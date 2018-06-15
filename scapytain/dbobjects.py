#! /usr/bin/env python

## This file is part of Scapytain
## See http://www.secdev.org/projects/scapytain for more informations
## Copyright (C) Philippe Biondi <phil@secdev.org>
## This program is published under a GPLv2 license

from __future__ import print_function

import sys, os, glob, json, copy
from sqlobject import *
import logging
import re
import six
log = logging.getLogger("scapytain")

sqlmeta.style = styles.MixedCaseStyle()

DB_VERSION = "1.0"

class Meta(SQLObject):
    tag = StringCol()
    value = StringCol()

class Test_Plan(SQLObject):
    reference = UnicodeCol()
    name = UnicodeCol()
    description = UnicodeCol(default="")
    objectives = MultipleJoin('Objective')
    sections = MultipleJoin('Section')
    campaigns = RelatedJoin('Campaign')
    keywords = UnicodeCol(default="")

class Section(SQLObject):
    name = UnicodeCol()
    test_plan = ForeignKey('Test_Plan', cascade=False)
    objectives = MultipleJoin('Objective')

class Objective(SQLObject):
    test_plan = ForeignKey('Test_Plan', cascade=False)
    section = ForeignKey('Section', cascade="null", default=None)
    reference = UnicodeCol()
    name = UnicodeCol()
    description = UnicodeCol(default="")
    rationale = UnicodeCol(default="")
    priority = IntCol(default=0)
    applicable = BoolCol(default=True)
    tests = RelatedJoin('Test')
    objective_results = MultipleJoin('Objective_Result')
    keywords = UnicodeCol(default="")
    
class Test(SQLObject):
    test_spec = ForeignKey('Test_Spec', cascade=False)
    objectives = RelatedJoin('Objective')
    results = MultipleJoin('Result')
    code = UnicodeCol()
    version = IntCol()
    comment = UnicodeCol(default="")

class Test_Spec(SQLObject):
    test_group = ForeignKey('Test_Group', cascade="null", default=None)
    reference = UnicodeCol()
    name = UnicodeCol()
    description = UnicodeCol(default="")
    expected_result = UnicodeCol(default="")
    tests = MultipleJoin('Test', orderBy='version')
    parents = RelatedJoin("Test_Spec", joinColumn="parents", otherColumn="children", addRemoveName="Parent")
    children = RelatedJoin("Test_Spec", joinColumn="children", otherColumn="parents",addRemoveName="Child", createRelatedTable=False)
    keywords = UnicodeCol(default="")

class Test_Group(SQLObject):
    name = UnicodeCol()
    tests = MultipleJoin('Test_Spec')

class Test_Mean(SQLObject):
    reference = UnicodeCol()
    name = UnicodeCol()
    description = UnicodeCol(default="")
    image = BLOBCol(default="")
    image_mime = StringCol(default="")
    code_init = UnicodeCol()
    keywords_mode = IntCol(default=0)
    keywords = UnicodeCol(default="")

class Campaign(SQLObject):
    test_plans = RelatedJoin('Test_Plan')
    reference = UnicodeCol()
    name = UnicodeCol()
    description = UnicodeCol(default="")
    test_mean = ForeignKey('Test_Mean', cascade=False, default=None)
    campaign_runs = MultipleJoin('Campaign_Run')

class Campaign_Run(SQLObject):
    campaign = ForeignKey('Campaign', cascade=False)
    reference = UnicodeCol()
    name = UnicodeCol()
    test_mean = ForeignKey('Test_Mean', cascade=False, default=None)
    description = UnicodeCol(default="")
    context = UnicodeCol(default="")
    date = DateTimeCol(default=DateTimeCol.now)
    test_plan_results = MultipleJoin('Test_Plan_Result')
    results = MultipleJoin('Result')

class Test_Plan_Result(SQLObject):
    test_plan = ForeignKey('Test_Plan', cascade=False)
    objective_results = MultipleJoin('Objective_Result')
    campaign_run = ForeignKey('Campaign_Run', cascade=False)

class Objective_Result(SQLObject):
    results = RelatedJoin('Result')
    objective = ForeignKey('Objective', cascade=False)
    test_plan_result = ForeignKey('Test_Plan_Result', cascade=False)

class Result(SQLObject):
    campaign_run = ForeignKey('Campaign_Run', cascade=False)
    test = ForeignKey('Test', cascade=False)
    completed = BoolCol(default=False)
    is_dependency = BoolCol(default=False)
    date = DateTimeCol(default=DateTimeCol.now)
    output = UnicodeCol(default=u'')
    status = ForeignKey('Status', cascade=False)
    objective_results = RelatedJoin('Objective_Result')

class Status(SQLObject):
    status = UnicodeCol()
    css_class = UnicodeCol()
    

def open_database(db, create=False):
    if "://" not in db:
        db = "sqlite:/"+os.path.abspath(db)
    log.info("Opening DB [%s]" % db)
    sqlhub.processConnection=connectionForURI(db)
    if not create:
        try:
            res = Meta.selectBy(tag="dbversion")
            if res[0].value != DB_VERSION:
                raise ScapytainException("Found database version %s while expected version %s" %
                                         (res[0].value, DB_VERSION))
        except ScapytainException:
            raise
        except Exception,e:
            raise ScapytainException("Error while checking database version (%s)" % e)
        
    
    
DO_TXN = sqlhub.doInTransaction

def get_all_tables():
    return [x for x in globals().values() if isinstance(x, type) and issubclass(x, SQLObject) and x != SQLObject]

def create_tables():
    for o in get_all_tables():
        print("Creating table [%s]" % o.__name__)
        o.createTable()
    print("Populating Meta table")
    Meta(tag="dbversion", value=DB_VERSION)
    print("Populating status table")
    Status(status="Not done", css_class="test_not_done")
    Status(status="Stopped", css_class="test_stopped")
    Status(status="Failed", css_class="test_failed")
    Status(status="Passed", css_class="test_passed")
    Status(status="Outdated failed", css_class="test_outdated_failed")
    Status(status="Outdated passed", css_class="test_outdated_passed")
    Status(status="Dependency Failed", css_class="test_dependency_failed")
    Status(status="Skipped", css_class="test_skipped")
    

def dump_table(t):
    import pprint
    cols = t.sqlmeta.columns.keys()
    table=[cols]
    print("Dumping table [%s]" % t.__name__)
    for row in t.select():
        table.append([getattr(row,k) for k in cols])
    pprint.pprint(table)

def counter(fmt="%i",start=0):
    i=start
    while 1:
        yield fmt%i
        i += 1


def import_uts_file(uts_file, *args,**kargs):
    uts_data = open(uts_file).read()
    return import_uts_data(uts_data, *args,**kargs)

def import_uts_data(uts_data, test_plan=None, test_plan_ref=None, testref="TEST%03i", objref="OBJ%03i", add_dependency=False):
    testrefc=counter(testref)
    prev_test_spec = None
    test_spec = None
    test = None
    group = None
    obj = None
    objrefc=counter(objref)
    if test_plan is None:
        if test_plan_ref is None:
            test_plan_ref = "No ref yet"
        test_plan = Test_Plan(reference=test_plan_ref, name="Import from file, no name yet")

    for l in uts_data.splitlines(True):
        if not l or l[0] == '#':
            continue
        if l[0] == "~":
            if test_plan:
                if prev_test_spec is not None:
                    prev_test_spec.keywords = l[1:].strip()
                elif obj is not None:
                    obj.keywords = l[1:].strip()
                elif test_plan:
                    test_plan.keywords = l[1:].strip()
        elif l[0] == "%":
            if test_plan:
                test_plan.name = l[1:].strip()
        elif l[0] == "+":
            group = Test_Group(name=l[1:].strip())
            prev_test_spec = test_spec = None
            if test_plan:
                obj = Objective(test_plan=test_plan, name=l[1:].strip(), reference=objrefc.next())
        elif l[0] == "=": # XXX: TODO: TXN
            test_spec = Test_Spec(reference=testrefc.next(), name=l[1:].strip(), test_group=group)
            try:
                test = Test(code="",  test_spec=test_spec, version=1)
            except:
                test_spec.destroySelf()
                raise
            if obj:
                obj.addTest(test)
            if add_dependency and prev_test_spec:
                test_spec.addParent(prev_test_spec)
            prev_test_spec = test_spec
        elif l[0] == "*":
            if test_spec is not None:
                test_spec.description += l[1:]
        else:
            if test is not None:
                test.code += l

def _resolve_testfiles(testfiles, scapy):
    for tfile in testfiles[:]:
        if "*" in tfile:
            testfiles.remove(tfile)
            testfiles.extend(glob.glob(os.path.abspath(os.path.join(scapy, tfile))))
    return testfiles

def import_utsc_data(utsc_file, reference=None, test_mean=None):
    with open(utsc_file, "r") as f:
        utsc_data = f.read()
    name = os.path.split(utsc_file)[1]
    # scapy/test/config/ourfile.utsc ==> folder of the file + 2 upper to get the scapy folder
    scapy = os.path.abspath(os.path.join(os.path.split(utsc_file)[0], os.pardir, os.pardir))
    if not os.path.isdir(scapy):
        raise IOError("The file must be located in the scapy/test/config folder")
    if test_mean is None:
        if reference is None:
            reference = "No ref yet"
        test_mean = Test_Mean(reference=reference, name=name, code_init="")
    
    data = json.loads(utsc_data)
    testfiles = []
    code_init = []
    code_init.append("os.environ['SCAPY_ROOT_DIR'] = '" + scapy + "'")
    if "kw_ok" in data:
        test_mean.keywords = " ".join(data["kw_ok"])
        test_mean.keywords_mode = 0
    elif "kw_ko" in data:
        test_mean.keywords = " ".join(data["kw_ko"])
        test_mean.keywords_mode = 1
    if "preexec" in data:
        preexec = data["preexec"]
        for prex in six.iterkeys(copy.copy(preexec)):
            if "*" in prex:
                pycode = preexec[prex]
                del preexec[prex]
                for gl in glob.iglob(prex):
                    _pycode = pycode.replace("%name%", os.path.splitext(os.path.split(gl)[1])[0])
                    preexec[gl] = _pycode
        code_init.extend(preexec.values())
        if "global_preexec" in preexec:
            global_preexec = data["global_preexec"]
            code_init.append(global_preexec)
    test_mean.code_init = "\n".join(list(set(code_init)))
    if "testfiles" in data:
        testfiles = data["testfiles"]
        testfiles = _resolve_testfiles(testfiles, scapy)
        if "remove_testfiles" in data:
            for t in _resolve_testfiles(data["remove_testfiles"], scapy):
                try:
                    testfiles.remove(t)
                except:
                    pass
        camp = Campaign(name=name, reference=test_mean.reference, test_mean=test_mean)
        for t in testfiles:
            name = os.path.split(t)[1]
            test_plan = Test_Plan(reference="Test %s" % name, name=name)
            import_uts_file(t, test_plan=test_plan, add_dependency=True)
            camp.addTest_Plan(test_plan)


def usage():
    print("""usage:
    dbobjects -h
    dbobjects [-D database] {-c|-d|-l}
    dbobjects [-D database] -U <file.uts> [-T <test_plan_ref> [-o <objref_fmt>]] [-t <testref_fmt>]
    -c: create the tables
    -d: dump all data
    -l: list tables
    -n: dry run
    -U: import UTscapy campaign file
    -T: test plan reference. If provided with -U, create a test plan for imported tests
    -o: objectives reference template (default: "OJB%03i")
    -t: test reference template (default: "TEST%03i")
    """, file=sys.stderr)

def main(argv, conf=None):
    import getopt
    import config
    if conf is None:
        conf = config.get_config()

    INTERACT,CREATE,LIST,DUMP,IMPORT_UTS = range(5)
    ACTION=None
    TABLES=[]
    DB=conf.database
    TESTPLANREF=None
    OBJREF="OBJ%03i"
    TESTREF="TEST%03i"
    DRYRUN=False
    
    try:
        opts = getopt.getopt(argv[1:],"hD:t:icdlU:T:o:t:n")
        for opt,optarg in opts[0]:
            if opt == "-h":
                usage()
                sys.exit(0)
            elif opt == "-D":
                DB = optarg
            elif opt == "-t":
                TABLES.append(optarg)
            elif opt == "-U":
                ACTION = IMPORT_UTS
                IMPORT_FILE = optarg
            elif opt == "-n":
                DRYRUN = True
            elif opt == "-o":
                OBJREF = optarg
            elif opt == "-T":
                TESTPLANREF = optarg
            elif opt == "-t":
                TESTREF = optarg
            else:
                ACTION = {"-i":INTERACT, "-d":DUMP, "-l":LIST, "-c":CREATE}.get(opt)
        if ACTION is None:
            raise getopt.GetoptError("No action provided")
    except getopt.GetoptError,e:
        print("ERROR: %s" % e, file=sys.stderr)
        sys.exit(-1)

    if ACTION == CREATE:
        dbdir = os.path.dirname(DB)
        if not os.path.exists(dbdir):
            os.makedirs(dbdir)
            print("Created directory [%s]" % dbdir)

    open_database(DB, create=(ACTION==CREATE))
    if ACTION == LIST:
        for o in get_all_tables():
            print(o.__name__)
    elif ACTION == CREATE:
        create_tables()
    elif ACTION == DUMP:
        if not TABLES:
            TABLES = get_all_tables()
        for t in TABLES:
            dump_table(t)
    elif ACTION == IMPORT_UTS:
        import_uts_file(IMPORT_FILE, test_plan_ref=TESTPLANREF, 
                        testref=TESTREF, objref=OBJREF)
    elif ACTION == INTERACT:
        import code,rlcompleter,readline
        readline.parse_and_bind("tab: complete")
        code.interact(local=globals())
            

    
if __name__ == "__main__":
    main(sys.argv)
