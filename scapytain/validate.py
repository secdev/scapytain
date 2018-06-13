## This file is part of Scapytain
## See http://www.secdev.org/projects/scapytain for more informations
## Copyright (C) Philippe Biondi <phil@secdev.org>
## This program is published under a GPLv2 license

from __future__ import absolute_import
import formencode
from formencode import validators
from formencode import compound
from . import dbobjects
from sqlobject import SQLObjectNotFound

# SQL objects
class SQLObjectId(formencode.FancyValidator):
    _sqlobject = None
    def _to_python(self, value, state):
        sqlid = validators.Int().to_python(value)
        try:
            return self._sqlobject.get(sqlid)
        except SQLObjectNotFound as e:
            raise formencode.Invalid(str(e), value, state)
    def _from_python(self, value, state):
        return value.id
            
class TestPlanId(SQLObjectId):
    _sqlobject = dbobjects.Test_Plan

class ObjectiveId(SQLObjectId):
    _sqlobject = dbobjects.Objective

class SectionId(SQLObjectId):
    _sqlobject = dbobjects.Section

class CampaignId(SQLObjectId):
    _sqlobject = dbobjects.Campaign

class TestId(SQLObjectId):
    _sqlobject = dbobjects.Test

class TestGroupId(SQLObjectId):
    _sqlobject = dbobjects.Test_Group

class ResultId(SQLObjectId):
    _sqlobject = dbobjects.Result

class CampaignRunId(SQLObjectId):
    _sqlobject = dbobjects.Campaign_Run

class TestSpecId(SQLObjectId):
    _sqlobject = dbobjects.Test_Spec

class TestMeanId(SQLObjectId):
    _sqlobject = dbobjects.Test_Mean

class SectionId(SQLObjectId):
    _sqlobject = dbobjects.Section


# HTML forms
class Test_Plan(formencode.Schema):
    reference = validators.UnicodeString(not_empty=True, strip=True, encoding='utf-8')
    name = validators.UnicodeString(not_empty=True, encoding='utf-8')
    description = validators.UnicodeString(encoding='utf-8')

class Objective(formencode.Schema):
    reference = validators.UnicodeString(not_empty=True, strip=True, encoding='utf-8')
    name = validators.UnicodeString(not_empty=True, encoding='utf-8')
    description = validators.UnicodeString(encoding='utf-8')
    section = compound.Any(validators.OneOf(["none","new"]), SectionId())    
    newsection = validators.UnicodeString(encoding='utf-8')    
    rationale = validators.UnicodeString(encoding='utf-8')
    priority = validators.Int(not_empty=True, encoding='utf-8')
    applicable = validators.Bool()
    
class Test_and_Spec(formencode.Schema):
    reference = validators.UnicodeString(not_empty=True, strip=True, encoding='utf-8')
    name = validators.UnicodeString(encoding='utf-8')
    test_group = compound.Any(validators.OneOf(["none","new"]), TestGroupId())    
    new_group = validators.UnicodeString(encoding='utf-8')    
    description = validators.UnicodeString(encoding='utf-8')
    expected_result = validators.UnicodeString(encoding='utf-8')
    code = validators.UnicodeString(encoding='utf-8')
    comment = validators.UnicodeString(encoding='utf-8')
    dependencies = formencode.ForEach(TestSpecId())

class Test_Code(formencode.Schema):
    code = validators.UnicodeString(encoding='utf-8')
    comment = validators.UnicodeString(encoding='utf-8')    

class Campaign(formencode.Schema):
    reference = validators.UnicodeString(not_empty=True, strip=True, encoding='utf-8')
    name = validators.UnicodeString(not_empty=True, encoding='utf-8')
    description = validators.UnicodeString(encoding='utf-8')
    test_mean = TestMeanId()
    test_plans = formencode.ForEach(TestPlanId())

class Campaign_Run(formencode.Schema):
    reference = validators.UnicodeString(not_empty=True, strip=True, encoding='utf-8')
    name = validators.UnicodeString(not_empty=True, encoding='utf-8')
    description = validators.UnicodeString(encoding='utf-8')
    test_mean = TestMeanId()
    context = validators.UnicodeString(encoding='utf-8')

class Objective_Tests(formencode.Schema):
    tcodes = formencode.ForEach(TestId())

class TestMean(formencode.Schema):
    reference = validators.UnicodeString(not_empty=True, strip=True, encoding='utf-8')
    name = validators.UnicodeString(not_empty=True, encoding='utf-8')
    description = validators.UnicodeString(encoding='utf-8')
    code_init = validators.UnicodeString(encoding='utf-8')
