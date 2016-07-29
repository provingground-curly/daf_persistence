# -*- coding: UTF-8 -*-
#!/usr/bin/env python

#
# LSST Data Management System
# Copyright 2016 LSST Corporation.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <http://www.lsstcorp.org/LegalNotices/>.
#

import collections
import copy
import os
import pyfits
import shutil
import types
import unittest
import uuid

import yaml

import lsst.utils.tests as utilsTests
import lsst.daf.persistence as dp
from lsst.daf.persistence import Policy
import lsst.utils.tests

def setup_module(module):
    lsst.utils.tests.init()

class ParentMapper(dp.Mapper):

    def __init__(self, root):
        self.root = root

    def __repr__(self):
        return 'ParentMapper(root=%s)' % self.root

    def map_raw(self, dataId, write):
        python = 'pyfits.HDUList'
        persistable = None
        storage = 'PickleStorage'
        path = os.path.join(self.root, 'data/input/raw')
        path = os.path.join(path, 'raw_v' + str(dataId['visit']) + '_f' + dataId['filter'] + '.fits.gz')
        if os.path.exists(path):
            return dp.ButlerLocation(python, persistable, storage, path, dataId, self)
        return None

    def bypass_raw(self, datasetType, pythonType, location, dataId):
        return pyfits.open(location.getLocations()[0])

    def query_raw(self, format, dataId):
        values = [{'visit':1, 'filter':'g'}, {'visit':2, 'filter':'g'}, {'visit':3, 'filter':'r'}]
        matches = []
        for value in values:
            match = True
            for item in dataId:
                if value[item] != dataId[item]:
                    match = False
                    break
            if match:
                matches.append(value)
        results = set()
        for match in matches:
            tempTup = []
            for word in format:
                tempTup.append(match[word])
            results.add(tuple(tempTup))
        return results

    def getDefaultLevel(self):
        return 'visit'

    def getKeys(self, datasetType, level):
        return {'filter': bytes, 'visit': int}

    def map_str(self, dataId, write):
        path = os.path.join(self.root, 'data/input/raw')
        path = os.path.join(path, 'raw_v' + str(dataId['str']) + '_f' + dataId['filter'] + '.fits.gz')
        if os.path.exists(path):
            return dp.ButlerLocation(str, None, 'PickleStorage', path, dataId, self)
        return None


class ChildrenMapper(dp.Mapper):

    def __init__(self, root):
        self.root = root

    def map_raw(self, dataId, write):
        python = 'pyfits.HDUList'
        persistable = None
        storage = 'FitsStorage'
        path = os.path.join(self.root, 'data/input/raw')
        path = os.path.join(path, 'raw_v' + str(dataId['visit']) + '_f' + dataId['filter'] + '.fits.gz')
        if write or os.path.exists(path):
            return dp.ButlerLocation(python, persistable, storage, path, dataId, self)
        return None

    def bypass_raw(self, datasetType, pythonType, location, dataId):
        return pyfits.open(location.getLocations()[0])

    def query_raw(self, format, dataId):
        return None
        # results = set()
        # return results

    def getDefaultLevel(self):
        return 'visit'

    def getKeys(self, datasetType, level):
        return {'filter': bytes, 'visit': int}


class TestBasics(unittest.TestCase):
    """Test case for basic functions of the repository classes."""

    def setUp(self):
        self.tearDown()

        inputRepoArgs = dp.RepositoryArgs(root='tests/butlerAlias',
                                          mapper=ParentMapper,
                                          tags='baArgs')
        # mode of output repos is write-only by default
        outputRepoArgs = dp.RepositoryArgs(root='tests/TestBasics/repoA',
                                           mapper=ChildrenMapper,
                                           mode='rw')
        self.butler = dp.Butler(inputs=inputRepoArgs, outputs=outputRepoArgs)

    def tearDown(self):
        if os.path.exists('tests/TestBasics'):
            shutil.rmtree('tests/TestBasics')
        if os.path.exists('tests/butlerAlias/repositoryCfg.yaml'):
            os.remove('tests/butlerAlias/repositoryCfg.yaml')
        if hasattr(self, "butler"):
            del self.butler

    def testGet(self):
        raw_image = self.butler.get('raw', {'visit':'2', 'filter':'g'})
        # in this case the width is known to be 1026:
        self.assertEqual(raw_image[1].header["NAXIS1"], 1026)

    def testSubset(self):
        subset = self.butler.subset('raw')
        self.assertEqual(len(subset), 3)

    def testGetKeys(self):
        keys = self.butler.getKeys('raw')
        self.assertEqual('filter' in keys, True)
        self.assertEqual('visit' in keys, True)
        self.assertEqual(keys['filter'], bytes)
        self.assertEqual(keys['visit'], int)

        keys = self.butler.getKeys('raw', tag='baArgs')
        self.assertEqual('filter' in keys, True)
        self.assertEqual('visit' in keys, True)
        self.assertEqual(keys['filter'], bytes)
        self.assertEqual(keys['visit'], int)

        keys = self.butler.getKeys('raw', tag=('baArgs', 'foo'))
        self.assertEqual('filter' in keys, True)
        self.assertEqual('visit' in keys, True)
        self.assertEqual(keys['filter'], bytes)
        self.assertEqual(keys['visit'], int)

        keys = self.butler.getKeys('raw', tag='foo')
        self.assertEqual(keys, None)

        keys = self.butler.getKeys('raw', tag=set(['baArgs', 'foo']))
        self.assertEqual('filter' in keys, True)
        self.assertEqual('visit' in keys, True)
        self.assertEqual(keys['filter'], bytes)
        self.assertEqual(keys['visit'], int)


    def testQueryMetadata(self):
        val = self.butler.queryMetadata('raw', ('filter',))
        val.sort()
        self.assertEqual(val, ['g', 'r'])

        val = self.butler.queryMetadata('raw', ('visit',))
        val.sort()
        self.assertEqual(val, [1, 2, 3])

        val = self.butler.queryMetadata('raw', ('visit',), dataId={'filter':'g'})
        val.sort()
        self.assertEqual(val, [1, 2])

        val = self.butler.queryMetadata('raw', ('visit',), dataId={'filter':'r'})
        self.assertEqual(val, [3])

        val = self.butler.queryMetadata('raw', ('filter',), dataId={'visit':1})
        self.assertEqual(val, ['g'])

        val = self.butler.queryMetadata('raw', ('filter',), dataId={'visit':2})
        self.assertEqual(val, ['g'])

        val = self.butler.queryMetadata('raw', ('filter',), dataId={'visit':3})
        self.assertEqual(val, ['r'])

        val = self.butler.queryMetadata('raw', ('visit',), dataId={'filter':'h'})
        self.assertEqual(val, [])

        dataId = dp.DataId({'filter':'g'}, tag='baArgs')
        val = self.butler.queryMetadata('raw', ('visit',), dataId={'filter':'g'})
        val.sort()
        self.assertEqual(val, [1, 2])

        dataId = dp.DataId({'filter':'g'}, tag='foo')
        val = self.butler.queryMetadata('raw', ('visit',), dataId=dataId)
        self.assertEqual(val, [])


    def testDatasetExists(self):
        # test the valeus that are expected to be true:
        self.assertEqual(self.butler.datasetExists('raw', {'filter':'g', 'visit':1}), True)
        self.assertEqual(self.butler.datasetExists('raw', {'filter':'g', 'visit':2}), True)
        self.assertEqual(self.butler.datasetExists('raw', {'filter':'r', 'visit':3}), True)

        # test a few values that are expected to be false:
        self.assertEqual(self.butler.datasetExists('raw', {'filter':'f', 'visit':1}), False)
        self.assertEqual(self.butler.datasetExists('raw', {'filter':'r', 'visit':1}), False)
        self.assertEqual(self.butler.datasetExists('raw', {'filter':'g', 'visit':3}), False)


##############################################################################################################
##############################################################################################################
##############################################################################################################

class MapperForTestWriting(dp.Mapper):
    def __init__(self, root):
        self.root = root

    def map_foo(self, dataId, write):
        python = TestObject
        persistable = None
        storage = 'PickleStorage'
        fileName = 'filename'
        for key, value in dataId.iteritems():
            fileName += '_' + key + str(value)
        fileName += '.txt'
        path = os.path.join(self.root, fileName)
        if not write and not os.path.exists(path):
            return None
        return dp.ButlerLocation(python, persistable, storage, path, dataId, self)


class AlternateMapper(object):
    def __init__(self):
        pass


class TestObject(object):
    def __init__(self, data):
        self.data = data

    def __eq__(self, other):
        return self.data == other.data

    def __repr__(self):
        return "TestObject(data=%r)" % self.data

class TestWriting(unittest.TestCase):
    """A test case for the repository classes.

    A test that
    1. creates repo with a peer repo, writes to those repos.
    2. reloads those output repos as a parents of new repos
       * does a read from from the repo (verifies parent search)
    3. writes to the new output repo and reloads it as a parent of a new repo
       * verifies masking
    4. reloads the repo from its persisted cfg
       * verifies reload from cfg
    """

    def tearDown(self):
        if os.path.exists('tests/TestWriting'):
            shutil.rmtree('tests/TestWriting')
        # del self.butler

    def testCreateAggregateAndLoadingAChild(self):
        """Tests putting a very basic pickled object in a variety of Repository configuration settings
        :return:
        """

        repoAArgs = dp.RepositoryArgs(mode='w',
                                      root='tests/TestWriting/repoA',
                                      mapper=MapperForTestWriting)
        repoBArgs = dp.RepositoryArgs(mode='w',
                                      root='tests/TestWriting/repoB',
                                      mapper=MapperForTestWriting)
        butlerAB = dp.Butler(outputs=[repoAArgs, repoBArgs])

        objA = TestObject('abc')
        butlerAB.put(objA, 'foo', {'val':1})
        objB = TestObject('def')
        butlerAB.put(objB, 'foo', {'val':2})

        # create butlers where the output repos are now input repos
        butlerC = dp.Butler(inputs=dp.RepositoryArgs(root='tests/TestWriting/repoA'))
        butlerD = dp.Butler(inputs=dp.RepositoryArgs(root='tests/TestWriting/repoB'))

        # # verify the objects exist by getting them
        self.assertEqual(objA, butlerC.get('foo', {'val':1}))
        self.assertEqual(objA, butlerC.get('foo', {'val':1}))
        self.assertEqual(objB, butlerD.get('foo', {'val':2}))
        self.assertEqual(objB, butlerD.get('foo', {'val':2}))


class TestMasking(unittest.TestCase):
    """A test case for the repository classes.

    A test that
    1. creates a repo, does a put
    2. creates a new butler, uses that repo as an input and creates a new read-write output repo
    3. gets from the input repo, modifies the dataset, and puts into the output repo
    4. does a get and verifies that the changed dataset is returned.
    """

    def tearDown(self):
        if os.path.exists('tests/TestMasking'):
            shutil.rmtree('tests/TestMasking')

    def test(self):
        repoAArgs = dp.RepositoryArgs(mode='w',
                                      root='tests/TestMasking/repoA',
                                      mapper=MapperForTestWriting)
        butler = dp.Butler(outputs=repoAArgs)
        obj0 = TestObject('abc')
        butler.put(obj0, 'foo', {'bar':1})
        del butler
        del repoAArgs

        repoBArgs = dp.RepositoryArgs(mode='rw',
                                      root='tests/TestMasking/repoB',
                                      mapper=MapperForTestWriting)
        butler = dp.Butler(inputs='tests/TestMasking/repoA', outputs=repoBArgs)
        obj1 = butler.get('foo', {'bar':1})
        self.assertEqual(obj0, obj1)
        obj1.data = "def"
        butler.put(obj1, 'foo', {'bar':1})
        obj2 = butler.get('foo', {'bar':1})
        self.assertEqual(obj1, obj2)


class TestMultipleOutputsPut(unittest.TestCase):
    """A test case for the repository classes.

    A test that
        1. creates 3 peer repositories and readers for them
        2. does a single put
        3. verifies that all repos received the put
    """

    def tearDown(self):
        if os.path.exists('tests/TestMultipleOutputsPut'):
            shutil.rmtree('tests/TestMultipleOutputsPut')

    def test(self):
        repoAArgs = dp.RepositoryArgs(root='tests/TestMultipleOutputsPut/repoA',
                                      mapper=MapperForTestWriting)
        repoBArgs = dp.RepositoryArgs(root='tests/TestMultipleOutputsPut/repoB',
                                      mapper=MapperForTestWriting)

        butler = dp.Butler(outputs=(repoAArgs, repoBArgs))
        obj0 = TestObject('abc')
        butler.put(obj0, 'foo', {'bar':1})

        for root in ('tests/TestMultipleOutputsPut/repoA', 'tests/TestMultipleOutputsPut/repoB'):
            butler = dp.Butler(inputs=root)
            self.assertEqual(butler.get('foo', {'bar':1}), obj0)


class TestMultipleInputs(unittest.TestCase):
    """A test case for the repository classes.

    A test that
    - create output 2 repos, write same & different data to them & close them
    - create a new butler with those repos as inputs
    - read data that was written to both repos:
        - verify data that was written to only one of each repo
        - verify dissimilar datasets with same id that were written to the repos

    """

    def tearDown(self):
        if os.path.exists('tests/TestMultipleInputs'):
            shutil.rmtree('tests/TestMultipleInputs')


    def test(self):
        objAbc = TestObject('abc')
        objDef = TestObject('def')
        objGhi = TestObject('ghi')
        objJkl = TestObject('jkl')

        repoAArgs = dp.RepositoryArgs(mode='w',
                                      root='tests/TestMultipleInputs/repoA',
                                      mapper=MapperForTestWriting)
        butler = dp.Butler(outputs=repoAArgs)
        butler.put(objAbc, 'foo', {'bar':1})
        butler.put(objDef, 'foo', {'bar':2})

        repoBArgs = dp.RepositoryArgs(mode='w',
                                      root='tests/TestMultipleInputs/repoB',
                                      mapper=MapperForTestWriting)
        butler = dp.Butler(outputs=repoBArgs)
        butler.put(objGhi, 'foo', {'bar':1}) # note different object with overlapping dataId with repoA
        butler.put(objJkl, 'foo', {'bar':3})


        # note repo order: A, B
        butler = dp.Butler(inputs=('tests/TestMultipleInputs/repoA', 'tests/TestMultipleInputs/repoB'))
        self.assertEqual(butler.get('foo', {'bar':1}), objAbc)
        self.assertEqual(butler.get('foo', {'bar':2}), objDef)
        self.assertEqual(butler.get('foo', {'bar':3}), objJkl)

        # note reversed repo order: B, A
        butler = dp.Butler(inputs=('tests/TestMultipleInputs/repoB', 'tests/TestMultipleInputs/repoA'))
        self.assertEqual(butler.get('foo', {'bar':1}), objGhi)
        self.assertEqual(butler.get('foo', {'bar':2}), objDef)
        self.assertEqual(butler.get('foo', {'bar':3}), objJkl)


class TestTagging(unittest.TestCase):
    """A test case for the tagging of repository classes.
    """

    def tearDown(self):
        if os.path.exists('tests/TestTagging'):
            shutil.rmtree('tests/TestTagging')


    def testOneLevelInputs(self):
        """
        1. put an object with the same ID but slightly different value into 2 repositories.
        2. use those repositories as inputs to a butler, and tag them
        3. make sure that the correct object is gotten for each of
            a. one tag
            b. the other tag
            c. no tag
        4. repeat step 3 but reverse the order of input cfgs to a new butler.
        5. use the butler from step 4 and write an output. The inputs will get recorded as parents of the
           output repo.
        6. create a new butler with a new overlapping repo, and verify that objects can be gotten from the
           other's parent repos via tagging.
        """
        objA = TestObject('a')
        objB = TestObject('b')

        # put objA in repo1:
        repo1Args = dp.RepositoryArgs(mode='rw',
                                      root='tests/TestTagging/repo1',
                                      mapper=MapperForTestWriting)
        butler = dp.Butler(outputs=repo1Args)
        butler.put(objA, 'foo', {'bar':1})
        del butler

        # put objB in repo2:
        repo2Args = dp.RepositoryArgs(mode='rw',
                                      root='tests/TestTagging/repo2',
                                      mapper=MapperForTestWriting)
        butler = dp.Butler(outputs=repo2Args)
        butler.put(objB, 'foo', {'bar':1})
        del butler
        del repo1Args
        del repo2Args

        # make the objects inputs of repos
        # and verify the correct object can ge fetched using the tag and not using the tag

        repo1Args = dp.RepositoryArgs(root='tests/TestTagging/repo1', tags='one')
        repo2Args = dp.RepositoryArgs(root='tests/TestTagging/repo2', tags='two')

        butler = dp.Butler(inputs=(repo1Args, repo2Args))
        self.assertEqual(butler.get('foo', dp.DataId({'bar':1}, tag='one')), objA)
        self.assertEqual(butler.get('foo', dp.DataId({'bar':1}, tag='two')), objB)
        self.assertEqual(butler.get('foo', {'bar':1}), objA)

        butler = dp.Butler(inputs=(repo2Args, repo1Args))
        self.assertEqual(butler.get('foo', dp.DataId(bar=1, tag='one')), objA)
        self.assertEqual(butler.get('foo', dp.DataId(bar=1, tag='two')), objB)
        self.assertEqual(butler.get('foo', dp.DataId(bar=1)), objB)

        # create butler with repo1 and repo2 as parents, and an output repo3.
        repo3Args = dp.RepositoryArgs(mode='rw',
                                      root='tests/TestTagging/repo3',
                                      mapper=MapperForTestWriting)
        butler = dp.Butler(inputs=(repo1Args, repo2Args), outputs=repo3Args)
        self.assertEqual(butler.get('foo', dp.DataId({'bar':1}, tag='one')), objA)
        self.assertEqual(butler.get('foo', dp.DataId({'bar':1}, tag='two')), objB)
        self.assertEqual(butler.get('foo', {'bar':1}), objA)
        # add an object to the output repo. note since the output repo mode is 'rw' that object is gettable
        # and it has first priority in search order. Other repos should be searchable by tagging.
        objC = TestObject('c')
        butler.put(objC, 'foo', {'bar':1})
        self.assertEqual(butler.get('foo', {'bar':1}), objC)
        self.assertEqual(butler.get('foo', dp.DataId({'bar':1}, tag='one')), objA)
        self.assertEqual(butler.get('foo', dp.DataId({'bar':1}, tag='two')), objB)
        del butler

        repo3Cfg = dp.Storage.getRepositoryCfg('tests/TestTagging/repo3')
        self.assertEqual(repo3Cfg.parents, ['tests/TestTagging/repo1',
                                            'tests/TestTagging/repo2'])

        # expand the structure to look like this:
        # ┌────────────────────────┐ ┌────────────────────────┐
        # │repo1                   │ │repo2                   │
        # │ tag:"one"              │ │ tag:"two"              │
        # │ TestObject('a')        │ │ TestObject('b')        │
        # │   at ('foo', {'bar:1'})│ │   at ('foo', {'bar:1'})│
        # └───────────┬────────────┘ └───────────┬────────────┘
        #             └─────────────┬────────────┘
        #              ┌────────────┴───────────┐ ┌────────────────────────┐
        #              │repo4                   │ │repo5                   │
        #              │ tag:"four"             │ │ tag:"five"             │
        #              │ TestObject('d')        │ │ TestObject('e')        │
        #              │   at ('foo', {'bar:2'})│ │   at ('foo', {'bar:1'})│
        #              └───────────┬────────────┘ └───────────┬────────────┘
        #                          └─────────────┬────────────┘
        #                                     ┌──┴───┐
        #                                     │butler│
        #                                     └──────┘


        repo4Args = dp.RepositoryArgs(mode='rw',
                                      root='tests/TestTagging/repo4',
                                      mapper=MapperForTestWriting)
        butler = dp.Butler(inputs=('tests/TestTagging/repo1', 'tests/TestTagging/repo2'), outputs=repo4Args)
        objD = TestObject('d')
        butler.put(objD, 'foo', {'bar':2})
        del butler

        repo5Cfg = dp.RepositoryArgs(mode='rw',
                                     root='tests/TestTagging/repo5',
                                     mapper=MapperForTestWriting)
        butler = dp.Butler(outputs=repo5Cfg)
        objE = TestObject('e')
        butler.put(objE, 'foo', {'bar':1})
        del butler

        repo4Args = dp.RepositoryArgs(cfgRoot='tests/TestTagging/repo4', tags='four')
        repo5Args = dp.RepositoryArgs(cfgRoot='tests/TestTagging/repo5', tags='five')
        butler = dp.Butler(inputs=(repo4Args, repo5Args))
        self.assertEqual(butler.get('foo', {'bar':1}), objA)
        self.assertEqual(butler.get('foo', {'bar':2}), objD)
        self.assertEqual(butler.get('foo', dp.DataId({'bar':1}, tag='four')), objA)
        self.assertEqual(butler.get('foo', dp.DataId({'bar':1}, tag='five')), objE)
        del butler

        butler = dp.Butler(inputs=(repo5Args, repo4Args))
        self.assertEqual(butler.get('foo', {'bar':1}), objE)
        self.assertEqual(butler.get('foo', {'bar':2}), objD)
        self.assertEqual(butler.get('foo', dp.DataId({'bar':1}, tag='four')), objA)
        self.assertEqual(butler.get('foo', dp.DataId({'bar':1}, tag='five')), objE)
        del butler


class TestMapperInference(unittest.TestCase):
    """A test for inferring mapper in the cfg from parent cfgs"""

    def tearDown(self):
        if os.path.exists('tests/TestMapperInference'):
            shutil.rmtree('tests/TestMapperInference')

    def testSingleParent(self):
        """
        creates a repo that:
          a. does not have a mapper specified in the cfg
          b. has a parent that does have a mapper specified in the cfg
        verifies that the child repo inherits the parent's mapper via inference.
        """
        repoACfg = dp.RepositoryCfg(root='tests/TestMapperInference/repoA',
                                    mapper=MapperForTestWriting,
                                    mapperArgs=None,
                                    parents=None)
        dp.Storage.putRepositoryCfg(repoACfg, 'tests/TestMapperInference/repoA')

        repoBArgs = dp.RepositoryArgs(mode='rw',
                                      root='tests/TestMapperInference/repoB')
        butler = dp.Butler(inputs='tests/TestMapperInference/repoA', outputs=repoBArgs)
        self.assertIsInstance(butler._repos.outputs()[0].repo._mapper, MapperForTestWriting)


    def testMultipleParentsSameMapper(self):
        """
        creates a repo that:
          a. does not have a mapper specified in the cfg
          b. has 2 parents that do have the same mapper specified in the cfg
        verifies that the child repo inherits the parent's mapper via inference.

        """
        repoACfg = dp.RepositoryCfg(root='tests/TestMapperInference/repoA',
                                    mapper=MapperForTestWriting,
                                    mapperArgs=None,
                                    parents=None)
        repoBCfg = dp.RepositoryCfg(root='tests/TestMapperInference/repoB',
                                    mapper=MapperForTestWriting,
                                    mapperArgs=None,
                                    parents=None)
        dp.Storage.putRepositoryCfg(repoACfg, 'tests/TestMapperInference/repoA')
        dp.Storage.putRepositoryCfg(repoBCfg, 'tests/TestMapperInference/repoB')

        repoCArgs = dp.RepositoryArgs(mode='w',
                                      root='tests/TestMapperInference/repoC')

        butler = dp.Butler(inputs=('tests/TestMapperInference/repoA', 'tests/TestMapperInference/repoB'),
                           outputs=repoCArgs)
        self.assertIsInstance(butler._repos.outputs()[0].repo._mapper, MapperForTestWriting)


    def testMultipleParentsDifferentMappers(self):
        """
        creates a repo that:
          a. does not have a mapper specified in the cfg
          b. has 2 parent repos that have different mappers
        verifies that the constructor raises a RuntimeError because the mapper can not be inferred.
        """
        repoACfg = dp.RepositoryCfg(root='tests/TestMapperInference/repoA',
                                    mapper=MapperForTestWriting,
                                    mapperArgs=None,
                                    parents=None)
        repoBCfg = dp.RepositoryCfg(root='tests/TestMapperInference/repoB',
                                    mapper=AlternateMapper,
                                    mapperArgs=None,
                                    parents=None)
        dp.Storage.putRepositoryCfg(repoACfg, 'tests/TestMapperInference/repoA')
        dp.Storage.putRepositoryCfg(repoBCfg, 'tests/TestMapperInference/repoB')

        repoCArgs = dp.RepositoryArgs(mode='w',
                                      root='tests/TestMapperInference/repoC')
        self.assertRaises(RuntimeError,
                          dp.Butler,
                          inputs=('tests/TestMapperInference/repoA', 'tests/TestMapperInference/repoB'),
                          outputs=repoCArgs)


class TestMovedRepositoryCfg(unittest.TestCase):
    """Test if a repository cfg is in-place (resides at root of the repository) and the cfg is moved, the
    deserialized cfg root should be the new location if the repository is moved.
    """

    def setUp(self):
        self.tearDown

    def tearDown(self):
        if os.path.exists('tests/TestMovedRepositoryCfg'):
            shutil.rmtree('tests/TestMovedRepositoryCfg')

    def test(self):
        butler = dp.Butler(outputs=dp.RepositoryArgs(root="tests/TestMovedRepositoryCfg/a",
                                                     mapper=MapperForTestWriting))
        del butler
        os.makedirs("tests/TestMovedRepositoryCfg/b")
        os.rename('tests/TestMovedRepositoryCfg/a/repositoryCfg.yaml',
                  'tests/TestMovedRepositoryCfg/b/repositoryCfg.yaml')
        butler = dp.Butler(inputs="tests/TestMovedRepositoryCfg/b")
        self.assertEqual(butler._repos.all()[0].cfg, dp.RepositoryCfg(root='tests/TestMovedRepositoryCfg/b',
                                                                      mapper=MapperForTestWriting,
                                                                      mapperArgs=None,
                                                                      parents=None))


class TestOutputAlreadyHasParent(unittest.TestCase):
    def setUp(self):
        self.tearDown

    def tearDown(self):
        if os.path.exists('tests/TestOutputAlreadyHasParent'):
            shutil.rmtree('tests/TestOutputAlreadyHasParent')

    def test(self):
        # create a rewpo where repo 'a' is a parent of repo 'b'
        butler = dp.Butler(outputs=dp.RepositoryArgs(root='tests/TestOutputAlreadyHasParent/a',
                                                     mapper=MapperForTestWriting))
        del butler
        butler = dp.Butler(inputs='tests/TestOutputAlreadyHasParent/a',
                           outputs='tests/TestOutputAlreadyHasParent/b')
        self.assertEqual(len(butler._repos.inputs()), 1)
        self.assertEqual(butler._repos.inputs()[0].cfg.root, 'tests/TestOutputAlreadyHasParent/a')
        self.assertEqual(len(butler._repos.outputs()), 1)
        self.assertEqual(butler._repos.outputs()[0].cfg.root, 'tests/TestOutputAlreadyHasParent/b')
        del butler

        # load that repo a few times, redundantly include 'a' as an input (redundant because it's implicitly
        # an input by being a parent of 'b')
        for i in range(4):
            butler = dp.Butler(inputs='tests/TestOutputAlreadyHasParent/a',
                               outputs=dp.RepositoryArgs(root='tests/TestOutputAlreadyHasParent/b',
                                                         mode='rw'))
            self.assertEqual(len(butler._repos.inputs()), 2)
            self.assertEqual(butler._repos.inputs()[0].cfg.root, 'tests/TestOutputAlreadyHasParent/b')
            self.assertEqual(butler._repos.inputs()[1].cfg.root, 'tests/TestOutputAlreadyHasParent/a')
            self.assertEqual(len(butler._repos.outputs()), 1)
            self.assertEqual(butler._repos.outputs()[0].cfg.root, 'tests/TestOutputAlreadyHasParent/b')
            cfg = dp.Storage.getRepositoryCfg('tests/TestOutputAlreadyHasParent/b')
            self.assertEqual(cfg, dp.RepositoryCfg(root='tests/TestOutputAlreadyHasParent/b',
                                                   mapper=MapperForTestWriting,
                                                   mapperArgs=None,
                                                   parents=['tests/TestOutputAlreadyHasParent/a']))

        # load the repo a few times and don't explicitly list 'a' as an input
        for i in range(4):
            butler = dp.Butler(outputs=dp.RepositoryArgs(root='tests/TestOutputAlreadyHasParent/b',
                                                         mode='rw'))
            self.assertEqual(len(butler._repos.inputs()), 2)
            self.assertEqual(butler._repos.inputs()[0].cfg.root, 'tests/TestOutputAlreadyHasParent/b')
            self.assertEqual(butler._repos.inputs()[1].cfg.root, 'tests/TestOutputAlreadyHasParent/a')
            self.assertEqual(len(butler._repos.outputs()), 1)
            self.assertEqual(butler._repos.outputs()[0].cfg.root, 'tests/TestOutputAlreadyHasParent/b')
            cfg = dp.Storage.getRepositoryCfg('tests/TestOutputAlreadyHasParent/b')
            self.assertEqual(cfg, dp.RepositoryCfg(root='tests/TestOutputAlreadyHasParent/b',
                                                   mapper=MapperForTestWriting,
                                                   mapperArgs=None,
                                                   parents=['tests/TestOutputAlreadyHasParent/a']))

        # load 'b' as 'read only' and make sure 'a' does not get used as an input.
        butler = dp.Butler(outputs='tests/TestOutputAlreadyHasParent/b')
        self.assertEqual(len(butler._repos.inputs()), 0)
        self.assertEqual(len(butler._repos.outputs()), 1)
        self.assertEqual(butler._repos.outputs()[0].cfg.root, 'tests/TestOutputAlreadyHasParent/b')
        cfg = dp.Storage.getRepositoryCfg('tests/TestOutputAlreadyHasParent/b')


class MemoryTester(lsst.utils.tests.MemoryTestCase):
    pass


if __name__ == '__main__':
    lsst.utils.tests.init()
    unittest.main()
