#! /usr/bin/env python

## This file is part of Scapytain
## See http://www.secdev.org/projects/scapytain for more informations
## Copyright (C) Philippe Biondi <phil@secdev.org>
## This program is published under a GPLv2 license

import os
import cherrypy
import formencode
from formencode import validators,variabledecode
from genshi.template import TemplateLoader
from genshi.filters import HTMLFormFiller
from genshi.builder import tag
import genshi
import trml2pdf
from dbobjects import *
from error import ScapytainException
import validate
from highlight import highlight_python
import scapy_proxy
import logging
import config
import sqlobject
import sortkeys
import difflib
import time,datetime
#from sqlobject import SQLObjectIntegrityError
# SQLObjectIntegrityError is not exported => dirty hack. XXX
SQLObjectIntegrityError = sqlobject.SQLObject.destroySelf.im_func.func_globals["SQLObjectIntegrityError"]

log = logging.getLogger("scapytain")

conf = config.get_config()

loader = TemplateLoader(conf.templates_path, auto_reload=True)
scapy=scapy_proxy.ScapyProxy(conf.scapyproxy_path, conf.scapy_path, conf.modules)


class Root(object):

    @cherrypy.expose
    def index(self):
        raise cherrypy.HTTPRedirect("/test_plan")

    @cherrypy.expose
    def help(self):
        return loader.load("help.xml").generate().render("html", doctype="html")

    @cherrypy.expose
    def test_plan(self, test_plan_id=None, sortkey=None, rev=False, extended_view=False):
        if test_plan_id is not None:
            test_plan = validate.TestPlanId().to_python(test_plan_id)
            sortkey,sortkey_getter=sortkeys.objectives.getter(sortkey)
            tmpl = loader.load("test_plan.xml")
            return tmpl.generate(test_plan=test_plan,sortkey=sortkey,rev=rev,extended_view=extended_view,
                                 sortkey_getter=sortkey_getter).render("html", doctype="html")
        else:            
            sortkey,sortkey_getter=sortkeys.test_plans.getter(sortkey)
            tmpl = loader.load("test_plans.xml")
            return tmpl.generate(sortkey_getter=sortkey_getter,sortkey=sortkey,rev=rev,
                                 test_plans=Test_Plan.select()).render("html", doctype="html")

    @cherrypy.expose
    def edit_test_plan(self, test_plan_id=None, uts_file=None, uts_dependency=False, **post_data):
        errors={}
        data={}
        test_plan = None
        action = "/edit_test_plan"
        if test_plan_id is not None:
            test_plan = validate.TestPlanId().to_python(test_plan_id)
            data = test_plan.sqlmeta.asDict()
            action += "/%i" % test_plan.id
            
        if cherrypy.request.method == 'POST':
            try:
                valid_data = validate.Test_Plan().to_python(post_data)
            except formencode.Invalid, e:
                errors = e.unpack_errors()
                data = post_data
            else:
                def txn(test_plan):
                    if test_plan is None:
                        test_plan=Test_Plan(**valid_data)
                    else:
                        test_plan.set(**valid_data)
                    if uts_file is not None:
                        import_uts_data(uts_data=uts_file.value, test_plan=test_plan, add_dependency=uts_dependency)
                    return test_plan
                test_plan = DO_TXN(txn,test_plan)
                raise cherrypy.HTTPRedirect("/test_plan/%i" % test_plan.id)

        tmpl = loader.load('edit_test_plan.xml')
        stream = tmpl.generate(action=action , errors=errors) | HTMLFormFiller(data=data)
        return stream.render('html', doctype='html')

    @cherrypy.expose
    def edit_sections(self, test_plan_id,  **post_data):
        errors={}
        data={}
        test_plan = validate.TestPlanId().to_python(test_plan_id)
        data = test_plan.sqlmeta.asDict()
            
        if cherrypy.request.method == 'POST':
            try:
                lst = [(validate.SectionId().to_python(k),v) for k,v in post_data.iteritems()]
            except formencode.Invalid, e:
                errors = e.unpack_errors()
                data = post_data
            else:
                def txn():
                    for s,sname in lst:
                        if sname:
                            s.name = sname
                        else:
                            s.destroySelf()
                DO_TXN(txn)
                raise cherrypy.HTTPRedirect("/test_plan/%i" % test_plan.id)

        tmpl = loader.load('edit_sections.xml')
        stream = tmpl.generate(test_plan=test_plan, errors=errors) | HTMLFormFiller(data=data)
        return stream.render('html', doctype='html')



    @cherrypy.expose
    def edit_objective(self, obj_id=None, test_plan_id=None, **post_data):
        errors={}
        data={}
        test_plan = None
        obj = None
        action = "/edit_objective"
        if test_plan_id is not None:
            test_plan = validate.TestPlanId().to_python(test_plan_id)
            action += "/0/%i" % test_plan.id
        elif obj_id is not None:
            obj = validate.ObjectiveId().to_python(obj_id)
            data = obj.sqlmeta.asDict()
            if obj.section:
                data["section"] = str(obj.section.id)
            action += "/%i" % obj.id
            test_plan = obj.test_plan
        else:
            raise ScapytainException("Missing objective Id or test plan Id")
            
        if cherrypy.request.method == 'POST':
            try:
                valid_data = validate.Objective().to_python(post_data)
            except formencode.Invalid, e:
                errors = e.unpack_errors()
                data = post_data
            else:
                def txn(obj):
                    newsec = valid_data.pop("newsection")
                    if valid_data["section"] == "new":
                        valid_data["section"] = Section(name=newsec, test_plan=test_plan)
                    elif valid_data["section"] == "none":
                        del(valid_data["section"])
                    if obj is None:
                        obj=Objective(test_plan=test_plan, **valid_data)
                    else:
                        obj.set(**valid_data)
                    return obj
                obj = DO_TXN(txn,obj)
                raise cherrypy.HTTPRedirect("/objective/%i" % obj.id)

        tmpl = loader.load('edit_objective.xml')
        stream = tmpl.generate(test_plan=test_plan, action=action , errors=errors) | HTMLFormFiller(data=data)
        return stream.render('html', doctype='html')

    @cherrypy.expose
    def objective(self, obj_id):
        obj = validate.ObjectiveId().to_python(obj_id)
        tmpl = loader.load('objective.xml')
        return tmpl.generate(obj=obj).render('html', doctype='html')


    @cherrypy.expose
    def test(self, tspec_id=None, diff="0",sortkey=None, rev=False, extended_view=False):
        if tspec_id is None:
            sortkey,sortkey_getter=sortkeys.tests.getter(sortkey)
            stream = loader.load('tests.xml').generate(tspecs=Test_Spec.select(),groups=Test_Group.select(),
	                                               sortkey=sortkey,rev=rev,sortkey_getter=sortkey_getter)
        else:
            diff=(diff != "0")
            differ=None
            if diff:
                differ=difflib.HtmlDiff()
            tspec = validate.TestSpecId().to_python(tspec_id)
            imagemap = self.get_dependencies_graph(tspec, format="cmapx").decode("utf-8")
            stream = loader.load('test.xml').generate(tspec=tspec,hl_python=highlight_python,imagemap=imagemap,
                                                      differ=differ,test_means=Test_Mean.select())
        return stream.render('html', doctype='html')

    def split_test_and_spec(self, tas):
        tst = {}
        spc = {}
        for k in tas:
            if k in ["reference","name","description","expected_result","test_group","new_group","dependencies"]:
                spc[k] = tas[k]
            else:
                tst[k] = tas[k]
        return spc,tst

    def outdate_result(self, res):
        if res.status.id == Status_Failed.id:
            res.status = Status_Outdated_Failed
        elif res.status.id == Status_Passed.id:
            res.status = Status_Outdated_Passed

    def undo_outdate_result(self, res):
        if res.status.id == Status_Outdated_Failed.id:
            res.status = Status_Failed
        elif res.status.id == Status_Outdated_Passed.id:
            res.status = Status_Passed

    def get_all_parents(self, deps, seen=None):
        if seen is None:
            seen = []
        for d in deps:
            if d not in seen:
                seen = self.get_all_parents(d.parents, seen)
                seen.append(d)
        return seen

    def get_all_children(self, deps, seen=None):
        if seen is None:
            seen = []
        for d in deps:
            if d not in seen:
                seen = self.get_all_children(d.children, seen)
                seen.append(d)
        return seen

    def get_dependencies_graph(self, tspec, format="png"):
        w,r = os.popen2("tee /tmp/toto.dot | dot -T%s" % format)
        out = lambda x:w.write(x.encode("utf-8"))

        label = lambda t:t.reference.replace('"','\"')
        id = lambda t:"t%i" % t.id
        node = lambda t: '\t%s [label="%s", href="/test/%i"]\n' % (id(t),label(t),t.id)
        link = lambda t,u: '\t%s -> %s\n' % (id(t),id(u))

        parents = self.get_all_parents(tspec.parents)
        children = self.get_all_children(tspec.children)
        
        out('digraph test_dep {\n')
        out('\tnode [shape="box", style="filled"];\n')
        
        # current node
        out('\tnode [fillcolor="#0099d8"];\n')
        out(node(tspec))

        # parent nodes
        out('\tnode [fillcolor="#a0e0a0"];\n')
        for p in parents:
            out(node(p))

        # children nodes
        out('\tnode [fillcolor="#e0a0a0"];\n')
        for c in children:
            out(node(c))

        for p in tspec.parents:
            out(link(p,tspec))
        for c in tspec.children:
            out(link(tspec,c))
        for p in parents:
            for pp in p.parents:
                out(link(pp,p))
        for c in children:
            for cc in c.children:
                out(link(c,cc))
        out("}\n")
        w.close()
        return r.read()

    @cherrypy.expose
    def test_graph(self, tspec_id):
        tspec = validate.TestSpecId().to_python(tspec_id)
        png = self.get_dependencies_graph(tspec, format="png")
        cherrypy.response.headers['Content-Type'] = "image/png"
        return png
        

    @cherrypy.expose
    def edit_test(self, tspec_id=None, obj_id=None, **post_data):
        errors={}
        data={}
        tspec = None
        obj = None
        action = "/edit_test"
        if obj_id is not None:
            obj = validate.ObjectiveId().to_python(obj_id)
            action += "/0/%i" % obj.id
        elif tspec_id is not None:
            tspec = validate.TestSpecId().to_python(tspec_id)
            data = tspec.sqlmeta.asDict()
            data.update(tspec.tests[-1].sqlmeta.asDict())
            if tspec.test_group:
                data["test_group"] = str(tspec.test_group.id)
            data["dependencies"] = [p.id for p in tspec.parents]
            action += "/%i" % tspec.id
            
        if cherrypy.request.method == 'POST':
            try:
                valid_data = validate.Test_and_Spec().to_python(post_data)
                dependencies = valid_data.pop("dependencies")
                if tspec and tspec in self.get_all_parents(dependencies):
                    raise formencode.Invalid(msg="", value=0, state=None,
                                             error_dict={"dependencies":
                                                         formencode.Invalid(msg="Cyclic reference",
                                                                            value=0, state=None)})
            except formencode.Invalid, e:
                errors = e.unpack_errors()
                data = post_data
            else:
                def txn(tspec):
                    spc_data,tst_data = self.split_test_and_spec(valid_data)
                    new_group = spc_data.pop("new_group")
                    if spc_data["test_group"] == "new":
                        spc_data["test_group"] = Test_Group(name=new_group)
                    elif spc_data["test_group"] == "none":
                        spc_data["test_group"] = None
                        
                    if tspec is None:
                        tspec = Test_Spec(**spc_data)
                        tcode = Test(test_spec=tspec, version=1 , **tst_data)
                    else:
                        tspec.set(**spc_data)
                        tcode = tspec.tests[-1]
                        if not tcode.code.strip() or tcode.code == tst_data["code"]:
                            tcode.set(**tst_data)
                        else:
                            for tst in tspec.tests:
                                for res in tst.results:
                                    self.outdate_result(res)
                            tcode=Test(test_spec=tspec, version=tcode.version+1,**tst_data)
                    for d in tspec.parents:
                        if d not in dependencies:
                            tspec.removeParent(d)
                    for d in dependencies:
                        if d not in tspec.parents:
                            tspec.addParent(d)
                    
                    if obj:
                        obj.addTest(tcode)
                    return tspec

                tspec = DO_TXN(txn,tspec)
                        
                raise cherrypy.HTTPRedirect("/test/%i" % tspec.id)

        tmpl = loader.load('edit_test.xml')
        stream = tmpl.generate(action=action , errors=errors, obj=obj,
                               tspecs=Test_Spec.select(Test_Spec.q.id != (tspec and tspec.id or 0)),
                               test_groups=Test_Group.select()) | HTMLFormFiller(data=data)
        return stream.render('html', doctype='html')


    @cherrypy.expose
    def edit_test_code(self, tspec_id, version=0, tmean_id=None, tryit=None, submit=None, **post_data):
        errors={}
        tspec = validate.TestSpecId().to_python(tspec_id)
        version = validators.Int(min=0, max=len(tspec.tests)).to_python(version)
        tcode = tspec.tests[version-1]
        data = {"code":tcode.code, "comment":tcode.comment}
        results=result=status=exn=status=not_done=None
        if tmean_id == "none":
            tmean_id = None
        tmean = validate.TestMeanId().to_python(tmean_id)
        init=None
        if tmean:
            init=tmean.code_init
        

        if cherrypy.request.method == 'POST':
            try:
                valid_data = validate.Test_Code().to_python(post_data)
            except formencode.Invalid, e:
                errors = e.unpack_errors()
                data = post_data
            else:
                if tryit is not None:
                    data = valid_data
                    class fake_tcode:
                        test_spec = tspec
                        code = valid_data["code"]
                        version = len(tspec.tests)+1
                        comment = valid_data["comment"]
                        
                    deps = [x.tests[-1] for x in self.get_all_parents([tspec])]
                    deps[-1]  = fake_tcode
                    test_runner = scapy.run_tests_from_tcode(deps,init=init)
                    results = []
                    for t,(res_val,res,exn) in test_runner:
                        results.append((t,[Status_Failed,Status_Passed,Status_Stopped][res_val],res))
                        if res_val != 1:
                            break
            
                    not_done = deps[len(results):]
            
                    if t != fake_tcode:
                        status = Status_Dependency_Failed
                        exn = None
                        not_done.pop()
                        result = None
                    else:
                        _,status,result = results.pop()
            
                    results.reverse()
                    not_done.reverse()

                elif submit is not None:
                    latest_tcode = tspec.tests[-1]
                    if latest_tcode.code != post_data["code"]:
                        if not latest_tcode.code.strip():
                            latest_tcode.set(**valid_data)
                        else:
                            v=len(tspec.tests)+1
                            t=Test(test_spec=tspec, version=v, **valid_data)
                        for tst in tspec.tests:
                            for res in tst.results:
                                self.outdate_result(res)
                        
                    raise cherrypy.HTTPRedirect("/test/%i" % tspec.id)

        tmpl = loader.load('edit_test_code.xml')
        stream = tmpl.generate(errors=errors, tspec=tspec, tcode=tcode, test_means=Test_Mean.select(),
                               results=results, result=result, exn=exn, not_done=not_done, status=status,
                               ) | HTMLFormFiller(data=data)
        return stream.render('html', doctype='html')

    @cherrypy.expose
    def run_test(self, tspec_id, version=0, tmean_id=None):
        tspec = validate.TestSpecId().to_python(tspec_id)
        if tmean_id == "none":
            tmean_id = None
        tmean = validate.TestMeanId().to_python(tmean_id)
        init=None
        if tmean:
            init=tmean.code_init
        version = validators.Int(min=0, max=len(tspec.tests)).to_python(version)
        tcode = tspec.tests[version-1]

        deps = [x.tests[-1] for x in self.get_all_parents([tspec])]
        deps[-1]  = tcode
        test_runner = scapy.run_tests_from_tcode(deps, init=init)
        results = []
        for t,(res_val,res,exn) in test_runner:
            results.append((t,[Status_Failed,Status_Passed,Status_Stopped][res_val],res))
            if res_val != 1:
                break

        not_done = deps[len(results):]

        if t != tcode:
            status = Status_Dependency_Failed
            exn = None
            not_done.pop()
            result = None
        else:
            _,status,result = results.pop()

        results.reverse()
        not_done.reverse()
        tmpl = loader.load('test_result.xml')
        return tmpl.generate(tspec=tspec, tcode=tcode, hl_test=highlight_python(tcode.code),
                             status=status, exn=exn, result=result, results=results, 
                             not_done=not_done).render('html', doctype='html')
        
    @cherrypy.expose
    def edit_obj_tests(self, obj_id, **post_data):
        errors={}
        obj = validate.ObjectiveId().to_python(obj_id)
            
        if cherrypy.request.method == 'POST':
            try:
                valid_data = validate.Objective_Tests().to_python(post_data)
            except formencode.Invalid, e:
                errors = e.unpack_errors()
                data = post_data
            else:
                def txn():
                    tcodes = valid_data["tcodes"]
                    for tcode in obj.tests:
                        if tcode not in tcodes:
                            obj.removeTest(tcode)
                    for tcode in tcodes:
                        if tcode not in obj.tests:
                            obj.addTest(tcode)
                DO_TXN(txn)
                raise cherrypy.HTTPRedirect("/objective/%i" % obj.id)
        else:
            data = {"tcodes": [tcode.id for tcode in obj.tests]}
            tcodes_list = []
            upgraded_tests=False
            
            objspecs = [tc.test_spec for tc in obj.tests]
            for tspec in Test_Spec.select():
                latest_tcode = tspec.tests[-1]
                upgr = False
                if tspec in objspecs:
                    for tcode in obj.tests:
                        if tcode.test_spec == tspec and tcode != latest_tcode:
                            tcodes_list.append((True, tcode))
                            upgr = True
                tcodes_list.append((upgr, latest_tcode))
                upgraded_tests |= upgr
                            
        tmpl = loader.load('edit_obj_tests.xml')
        stream = tmpl.generate(obj=obj , tcodes_list=tcodes_list, data=data, errors=errors, upgraded_tests=upgraded_tests) | HTMLFormFiller(data=data)
        return stream.render('html', doctype='html')


    @cherrypy.expose
    def test_mean(self, test_mean_id=None, sortkey=None, rev=False):
        if test_mean_id is not None:
            test_mean = validate.TestMeanId().to_python(test_mean_id)
            tmpl = loader.load("test_mean.xml")
            return tmpl.generate(tm=test_mean).render("html", doctype="html")
        else:            
            sortkey,sortkey_getter=sortkeys.test_means.getter(sortkey)
            tmpl = loader.load("test_means.xml")
            return tmpl.generate(sortkey=sortkey,rev=rev,sortkey_getter=sortkey_getter,
                                 test_means=Test_Mean.select()).render("html", doctype="html")

    @cherrypy.expose
    def test_mean_image(self, test_mean_id):
        test_mean = validate.TestMeanId().to_python(test_mean_id)
        cherrypy.response.headers['Content-Type'] = test_mean.image_mime
        return test_mean.image
        


    @cherrypy.expose
    def edit_test_mean(self, test_mean_id=None, image=None, **post_data):
        errors={}
        data={}
        test_mean = None
        action = "/edit_test_mean"
        if test_mean_id is not None:
            test_mean = validate.TestMeanId().to_python(test_mean_id)
            data = test_mean.sqlmeta.asDict()
            action += "/%i" % test_mean.id
            
        if cherrypy.request.method == 'POST':
            try:
                valid_data = validate.TestMean().to_python(post_data)
            except formencode.Invalid, e:
                errors = e.unpack_errors()
                data = post_data
            else:
                def txn(test_mean):
                    if test_mean is None:
                        test_mean=Test_Mean(**valid_data)
                    else:
                        test_mean.set(**valid_data)
    
                    if image is not None and image.value:
                        test_mean.set(image=image.value, image_mime=image.type)
                    return test_mean
                test_mean = DO_TXN(txn,test_mean)
                raise cherrypy.HTTPRedirect("/test_mean/%i" % test_mean.id)

        tmpl = loader.load('edit_test_mean.xml')
        stream = tmpl.generate(action=action , errors=errors) | HTMLFormFiller(data=data)
        return stream.render('html', doctype='html')






    @cherrypy.expose
    def campaign(self, camp_id=None, sortkey=None, rev=False):
        if camp_id is None:
            sortkey,sortkey_getter=sortkeys.campaigns.getter(sortkey)
            stream = loader.load('campaigns.xml').generate(campaigns=Campaign.select(),
                                                           sortkey=sortkey,rev=rev,sortkey_getter=sortkey_getter)
        else:
            camp = validate.CampaignId().to_python(camp_id)
            sortkey,sortkey_getter=sortkeys.campaign_runs.getter(sortkey)
            stream = loader.load('campaign.xml').generate(camp=camp,sortkey=sortkey,rev=rev,sortkey_getter=sortkey_getter)
        return stream.render('html', doctype='html')

    @cherrypy.expose
    def compare_runs(self, camp_id):
        camp = validate.CampaignId().to_python(camp_id)
        return loader.load('compare_runs.xml').generate(camp=camp).render('html', doctype='html')

    @cherrypy.expose
    def edit_campaign(self, camp_id=None, **post_data):
        errors={}
        data={}
        camp = None
        action = "/edit_campaign"
        if camp_id is not None:
            camp = validate.CampaignId().to_python(camp_id)
            data = camp.sqlmeta.asDict()
            if camp.test_mean:
                data["test_mean"] = camp.test_mean.id
            data["test_plans"] = [str(x.id) for x in camp.test_plans]
            action += "/%i" % camp.id
            
        if cherrypy.request.method == 'POST':
            try:
                if post_data["test_mean"] == "none":
                    post_data["test_mean"] = None
                valid_data = validate.Campaign().to_python(post_data)
            except formencode.Invalid, e:
                errors = e.unpack_errors()
                data = post_data
            else:
                def txn(camp):
                    test_plans = valid_data.pop("test_plans")
                    if camp is None:
                        camp=Campaign(**valid_data)
                    else:
                        camp.set(**valid_data)
                    for l in camp.test_plans:
                        if l not in test_plans: 
                            camp.removeTest_Plan(l)
                    for l in test_plans:
                        if l not in camp.test_plans:
                            camp.addTest_Plan(l)
                    return camp
                camp = DO_TXN(txn,camp)
                raise cherrypy.HTTPRedirect("/campaign/%i" % camp.id)

        tmpl = loader.load('edit_campaign.xml')
        stream = tmpl.generate(test_plans=Test_Plan.select(), test_means=Test_Mean.select(),
                               action=action , errors=errors) | HTMLFormFiller(data=data)
        return stream.render('html', doctype='html')


    def resolve_run_dependencies(self,run):
        tcodes = [r.test for r in run.results]
        all_deps = self.get_all_parents(r.test.test_spec for r in run.results)
        for tspec in all_deps:
            tcode = tspec.tests[-1]
            if tcode not in tcodes:
                Result(campaign_run=run, test=tcode, status=Status_Not_Done, is_dependency=True)
        

    @cherrypy.expose
    def edit_run(self, run_id=None, camp_id=None, **post_data):
        errors={}
        data={}
        camp = None
        run = None
        action = "/edit_run"
        if camp_id is not None:
            camp = validate.CampaignId().to_python(camp_id)
            action += "/0/%i" % camp.id
            data["reference"] = camp.reference+"-run%02i" % len(list(camp.campaign_runs))
            if camp.test_mean:
                data["test_mean"] = camp.test_mean.id
        elif run_id is not None:
            run = validate.CampaignRunId().to_python(run_id)
            data = run.sqlmeta.asDict()
            action += "/%i" % run.id
            camp = run.campaign
            if run.test_mean:
                data["test_mean"] = run.test_mean.id
        else:
            raise ScapytainException("Missing campaign run Id or campaign Id")
            
        if cherrypy.request.method == 'POST':
            try:
                if post_data["test_mean"] == "none":
                    post_data["test_mean"] = None
                valid_data = validate.Campaign_Run().to_python(post_data)
            except formencode.Invalid, e:
                errors = e.unpack_errors()
                data = post_data
            else:
                def txn(run):
                    if run is None:
                        run=Campaign_Run(campaign=camp, **valid_data)
                        seen_tests = {}
                        for test_plan in camp.test_plans:
                            test_plan_r = Test_Plan_Result(campaign_run=run, test_plan=test_plan)
                            for obj in test_plan.objectives:
                                if obj.applicable:
                                    objr = Objective_Result(objective=obj, test_plan_result=test_plan_r)
                                    for tst in obj.tests:
                                        if tst not in seen_tests:
                                            seen_tests[tst] = Result(campaign_run=run, test=tst, completed=False,
                                                                     status=Status_Not_Done)
                                        objr.addResult(seen_tests[tst])
                        self.resolve_run_dependencies(run)
                    else:
                        run.set(**valid_data)
                    return run
                run = DO_TXN(txn,run)
                raise cherrypy.HTTPRedirect("/campaign_run/%i" % run.id)

        tmpl = loader.load('edit_run.xml')
        stream = tmpl.generate(camp=camp, action=action, test_means=Test_Mean.select(),
                               errors=errors) | HTMLFormFiller(data=data)
        return stream.render('html', doctype='html')

    @cherrypy.expose
    def run_from_failed(self, run_id):
        src_run = validate.CampaignRunId().to_python(run_id)
        camp = src_run.campaign
        def txn():
            dst_run = Campaign_Run(campaign=camp, test_mean=src_run.test_mean,
                                   reference=camp.reference+"-run%02i" % len(list(camp.campaign_runs)),
                                   name="Failed tests from %s" % src_run.name)
            seen_tests = {}
            for s_test_plan_r in src_run.test_plan_results:
                d_test_plan_r = None
                for sobjr in s_test_plan_r.objective_results:
                    dobjr = None
                    for res in sobjr.results:
                        if res.status.id not in [ Status_Passed.id, Status_Outdated_Passed.id ]:
                            tst = res.test
                            if tst not in seen_tests:
                                seen_tests[tst] = Result(campaign_run=dst_run, test=tst, completed=False,
                                                         status=Status_Not_Done)
                            if d_test_plan_r is None:
                                d_test_plan_r = Test_Plan_Result(campaign_run=dst_run, test_plan=s_test_plan_r.test_plan)
                            if dobjr is None:
                                dobjr = Objective_Result(objective=sobjr.objective, test_plan_result=d_test_plan_r)
                            dobjr.addResult(seen_tests[tst])
            self.resolve_run_dependencies(dst_run)
            return dst_run
        dst_run = DO_TXN(txn)
        raise cherrypy.HTTPRedirect("/campaign_run/%i" % dst_run.id)

    @cherrypy.expose
    def campaign_run(self, run_id):
        run = validate.CampaignRunId().to_python(run_id)
        return loader.load('campaign_run.xml').generate(run=run).render('html', doctype='html')

    @cherrypy.expose
    def result(self, resid):
        r = validate.ResultId().to_python(resid)
        tmpl = loader.load('campaign_result.xml')
        return tmpl.generate(res=r, hl_test=highlight_python(r.test.code)).render('html', doctype='html')


    @cherrypy.expose
    def launch_run(self, run_id):
        run = validate.CampaignRunId().to_python(run_id)
        results = [r for r in run.results if not r.completed]
        tm = run.test_mean
        init = None
        if tm:
            init=tm.code_init
        test_runner = scapy.run_tests_with_dependencies(results, lambda r:r.test, init=init)
        
        def add_test_runner(stream):
            for kind,data,pos in stream:
                yield (kind, data, pos)
                if kind == 'START' and data[1].get("id") == 'insert_tests_here':
                    for result,(res_val,res,exn) in test_runner:
                        result.set(output=res, date=datetime.datetime(*time.localtime()[:7]),
                                   status=[Status_Failed,Status_Passed,Status_Stopped,Status_Dependency_Failed][res_val])
                        if result.test != result.test.test_spec.tests[-1]:
                            self.outdate_result(result)
                        t = tag.tr(class_=result.status.css_class)
                        t(tag.td(tag.a("%s v%i/%i" % (result.test.test_spec.reference,
                                                      result.test.version,
                                                      len(list(result.test.test_spec.tests))),
                                       href="/test/%i" % result.test.test_spec.id)),
                          tag.td(result.test.test_spec.name),
                          tag.td(tag.a(result.status.status,
                                       href="/result/%i"%result.id)))
                        for x in t.generate():
                            yield x
                        if result.status.id == Status_Stopped.id:
                            t = tag.tr()
                            t(tag.td(tag.span(str(exn),class_="error"),
                                     tag.pre(genshi.Markup(result.output)),
                                     tag.form(tag.input(type="submit",value="Situation resolved, resume tests."),
                                              method="POST",action="/launch_run/%i"%run.id),
                                     colspan="3",align="center"))
                            for x in t.generate():
                                yield x
                            break
                        else:
                            result.completed=True
                    else:
                        t = tag.tr(tag.th("Test finished!",colspan="3",align="center"))
                        for x in t:
                            yield x
                            
        tmpl = loader.load('launch_run.xml')
        stream = tmpl.generate(run=run) | add_test_runner
        return stream.serialize('html', doctype='html')
    launch_run._cp_config = {'response.stream': True}


    @cherrypy.expose
    def upgrade_tests(self, test_plan_id):
        test_plan = validate.TestPlanId().to_python(test_plan_id)
        error=None
        if cherrypy.request.method == 'POST':
            try:
                def txn():
                    for o in test_plan.objectives:
                        for tcode in o.tests:
                            tspec = tcode.test_spec
                            latest_tcode = tspec.tests[-1]
                            if latest_tcode.id != tcode.id:
                                o.removeTest(tcode)
                                o.addTest(latest_tcode)
                DO_TXN(txn)
            except Exception,e:
                error=str(e)
            else:
                raise cherrypy.HTTPRedirect("/test_plan/%i"%test_plan.id)

        upgrade = []
        for o in test_plan.objectives:
            for tcode in o.tests:
                tspec = tcode.test_spec
                latest_tcode = tspec.tests[-1]
                if latest_tcode.id != tcode.id:
                    upgrade.append((o,tspec,tcode.version,latest_tcode.version))
        return loader.load('upgrade_tests.xml').generate(test_plan=test_plan,
                                                         menu={"test_plan":test_plan_id},
                                                         upgrade=upgrade).serialize('html', doctype='html')
        
    @cherrypy.expose
    def delete_test_plan(self, test_plan_id):
        test_plan = validate.TestPlanId().to_python(test_plan_id)
        error=None
        if cherrypy.request.method == 'POST':
            try:
                def txn():
                    for o in test_plan.objectives:
                        o.destroySelf()
                    for s in test_plan.sections:
                        s.destroySelf()
                    test_plan.destroySelf()
                DO_TXN(txn)
            except SQLObjectIntegrityError,e:
                error=str(e)
            else:
                raise cherrypy.HTTPRedirect("/test_plan/")
        objct = u"Test Plan %s (%s)" % (test_plan.reference,test_plan.name)
        return loader.load('delete.xml').generate(object=objct,error=error,
                                                  menu={'test_plan':test_plan_id},
                                                  test_plan=test_plan,
                                                  action="/delete_test_plan/%i"%test_plan.id).serialize('html', doctype='html')
        
    @cherrypy.expose
    def delete_objective(self, obj_id):
        obj = validate.ObjectiveId().to_python(obj_id)
        error=None
        if cherrypy.request.method == 'POST':
            test_plan = obj.test_plan
            try:
                DO_TXN(obj.destroySelf)
            except SQLObjectIntegrityError,e:
                error=str(e)
            else:
                raise cherrypy.HTTPRedirect("/test_plan/%i"%test_plan.id)
        objct = object=u"Objective %s (%s)" % (obj.reference,obj.name)
        action="/delete_objective/%i"%obj.id
        return loader.load('delete.xml').generate(object=objct,
                                                  menu={'objective':obj_id},
                                                  obj=obj,
                                                  error=error,action=action).serialize('html', doctype='html')
        
    
    @cherrypy.expose
    def delete_campaign(self, camp_id):
        camp = validate.CampaignId().to_python(camp_id)
        error=None
        if cherrypy.request.method == 'POST':
            try:
                DO_TXN(camp.destroySelf)
            except SQLObjectIntegrityError,e:
                error=str(e)
            else:
                raise cherrypy.HTTPRedirect("/campaign/")
        objct = object=u"Campaign %s (%s)" % (camp.reference,camp.name)
        action="/delete_campaign/%i"%camp.id
        return loader.load('delete.xml').generate(object=objct,
                                                  menu={'campaign':camp_id},
                                                  camp=camp,
                                                  error=error,action=action).serialize('html', doctype='html')
        
    @cherrypy.expose
    def delete_test(self, tspec_id):
        tspec = validate.TestSpecId().to_python(tspec_id)
        error=None
        if cherrypy.request.method == 'POST':
            try:
                def txn():
                    for tcode in tspec.tests:
                        tcode.destroySelf()
                    tspec.destroySelf()
                DO_TXN(txn)
            except SQLObjectIntegrityError,e:
                error=str(e)
            else:
                raise cherrypy.HTTPRedirect("/test/")
        objct = object=u"Test %s (%s)" % (tspec.reference,tspec.name)
        action="/delete_test/%i"%tspec.id
        return loader.load('delete.xml').generate(object=objct,
                                                  menu={"tspec":tspec_id},
                                                  tspec=tspec,
                                                  error=error,action=action).serialize('html', doctype='html')
        
    @cherrypy.expose
    def delete_test_version(self, tspec_id, version=0):
        tspec = validate.TestSpecId().to_python(tspec_id)
        version = validators.Int(min=0, max=len(tspec.tests)).to_python(version)
        tcode = tspec.tests[version-1]
        error=None
        if cherrypy.request.method == 'POST':
            try:
                def txn():
                    tcode.destroySelf()
                    if tspec.tests:
                        for tc in tspec.tests:
                            if tc.version > version:
                                tc.version -= 1
                        if version > len(tspec.tests):
                            latest_tcode = tspec.tests[-1]
                            for res in latest_tcode.results:
                                self.undo_outdate_result(res)
                    else:
                        Test(test_spec=tspec, version=1, code="")
                        
                DO_TXN(txn)
            except SQLObjectIntegrityError,e:
                error=str(e)
            else:
                raise cherrypy.HTTPRedirect("/test/%i"%tspec.id)
        objct = object=u"Version %i of test %s (%s)" % (version,tspec.reference,tspec.name)
        action="/delete_test_version/%i/%i"%(tspec.id,version)
        return loader.load('delete.xml').generate(object=objct,
                                                  menu={"tspec":tspec_id},
                                                  tspec=tspec,
                                                  error=error,action=action).serialize('html', doctype='html')
        
    @cherrypy.expose
    def delete_test_mean(self, tm_id):
        tm = validate.TestMeanId().to_python(tm_id)
        error=None
        if cherrypy.request.method == 'POST':
            try:
                DO_TXN(tm.destroySelf)
            except SQLObjectIntegrityError,e:
                error=str(e)
            else:
                raise cherrypy.HTTPRedirect("/test_mean/")
        objct = object=u"Test Mean %s (%s)" % (tm.reference,tm.name)
        action="/delete_test_mean/%i"%tm.id
        return loader.load('delete.xml').generate(object=objct,
                                                  menu={"test_mean":tm_id},
                                                  tm=tm,
                                                  error=error,action=action).serialize('html', doctype='html')
        
    

       
    @cherrypy.expose
    def report_project(self, projid):
        proj = validate.ProjectId().to_python(projid)
        tmpl = loader.load('report_project.rml')
        stream = tmpl.generate(proj=proj)
        cherrypy.response.headers['Content-Type'] = "application/pdf"
        cherrypy.response.headers['Content-Disposition'] = "attachement; filename=Project_%s.pdf" % proj.reference.replace(" ","_")
        return trml2pdf.parseString(stream.render())

def main(*args):
    db = conf.database
    import sqlobject
    def connectdb(thread_index):
        sqlobject.sqlhub.threadConnection = sqlobject.connectionForURI(db)

        try:
            res = Meta.selectBy(tag="dbversion")
            if res[0].value != DB_VERSION:
                raise ScapytainException("Found database version %s while expected version %s" %
                                         (res[0].value, DB_VERSION))
        except ScapytainException:
            raise
        except Exception,e:
            raise ScapytainException("Error while checking database version (%s)" % e)
            

        global Status_Not_Done,Status_Stopped,Status_Failed,Status_Passed
        global Status_Outdated_Failed,Status_Outdated_Passed,Status_Dependency_Failed
        
        Status_Not_Done=Status.get(1)
        Status_Stopped=Status.get(2)
        Status_Failed=Status.get(3)
        Status_Passed=Status.get(4)
        Status_Outdated_Failed=Status.get(5)
        Status_Outdated_Passed=Status.get(6)
        Status_Dependency_Failed=Status.get(7)

    cherrypy.engine.subscribe('start_thread', connectdb)

    cpconf = { '/static': { 'tools.staticdir.on': True, 'tools.staticdir.dir': 'static' },
               '/images': { 'tools.staticdir.on': True, 'tools.staticdir.dir': 'images' },
               '/favicon.ico': { 'tools.staticfile.on': True ,
                                 'tools.staticfile.filename': os.path.join(conf.static_path,'images/favicon.ico')},
               }
    if conf.auth:
        cpconf['/'] = { 'tools.digest_auth.on': True,
                        'tools.digest_auth.realm': 'Scapytain',
                        'tools.digest_auth.users': conf.users }

    cherrypy.tree.mount(Root(), "/", cpconf)
    cherrypy.config.update({
        'server.socket_port': conf.port,
        'tools.staticdir.root': conf.static_path,
        'server.ssl_certificate': conf.ssl_certificate,
        'server.ssl_private_key': conf.ssl_key,
        })
    if conf.production:
        cherrypy.config.update({"environment":"production"})

    cherrypy.engine.start()


if __name__ == "__main__":
    import sys
    main(*sys.argv[1:])
    
