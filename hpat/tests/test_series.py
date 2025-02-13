# -*- coding: utf-8 -*-

import unittest
import platform
import pandas as pd
import numpy as np
import pyarrow.parquet as pq
import hpat
from hpat.tests.test_utils import (
    count_array_REPs, count_parfor_REPs, count_array_OneDs, get_start_end)
from hpat.tests.gen_test_data import ParquetGenerator
from numba import types
from numba.config import IS_32BITS
from numba.errors import TypingError


_cov_corr_series = [(pd.Series(x), pd.Series(y)) for x, y in [
    (
        [np.nan, -2., 3., 9.1],
        [np.nan, -2., 3., 5.0],
    ),
    # TODO(quasilyte): more intricate data for complex-typed series.
    # Some arguments make assert_almost_equal fail.
    # Functions that yield mismaching results:
    # _column_corr_impl and _column_cov_impl.
    (
        [complex(-2., 1.0), complex(3.0, 1.0)],
        [complex(-3., 1.0), complex(2.0, 1.0)],
    ),
    (
        [complex(-2.0, 1.0), complex(3.0, 1.0)],
        [1.0, -2.0],
    ),
    (
        [1.0, -4.5],
        [complex(-4.5, 1.0), complex(3.0, 1.0)],
    ),
]]

min_float64 = np.finfo('float64').min
max_float64 = np.finfo('float64').max

test_global_input_data_float64 = [
    [1., np.nan, -1., 0., min_float64, max_float64],
    [np.nan, np.inf, np.NINF, np.NZERO]
]

min_int64 = np.iinfo('int64').min
max_int64 = np.iinfo('int64').max
max_uint64 = np.iinfo('uint64').max

test_global_input_data_integer64 = [
    [1, -1, 0],
    [min_int64, max_int64],
    [max_uint64]
]

test_global_input_data_numeric = test_global_input_data_integer64 + test_global_input_data_float64

test_global_input_data_unicode_kind4 = [
    'ascii',
    '12345',
    '1234567890',
    '¡Y tú quién te crees?',
    '🐍⚡',
    '大处着眼，小处着手。',
]

test_global_input_data_unicode_kind1 = [
    'ascii',
    '12345',
    '1234567890',
]


def _make_func_from_text(func_text, func_name='test_impl'):
    loc_vars = {}
    exec(func_text, {}, loc_vars)
    test_impl = loc_vars[func_name]
    return test_impl


def _make_func_use_binop1(operator):
    func_text = "def test_impl(A, B):\n"
    func_text += "   return A {} B\n".format(operator)
    return _make_func_from_text(func_text)


def _make_func_use_binop2(operator):
    func_text = "def test_impl(A, B):\n"
    func_text += "   A {} B\n".format(operator)
    func_text += "   return A\n"
    return _make_func_from_text(func_text)


def _make_func_use_method_arg1(method):
    func_text = "def test_impl(A, B):\n"
    func_text += "   return A.{}(B)\n".format(method)
    return _make_func_from_text(func_text)


GLOBAL_VAL = 2


class TestSeries(unittest.TestCase):

    def test_create1(self):
        def test_impl():
            df = pd.DataFrame({'A': [1, 2, 3]})
            return (df.A == 1).sum()
        hpat_func = hpat.jit(test_impl)

        self.assertEqual(hpat_func(), test_impl())

    @unittest.skip('Feature request: implement Series::ctor with list(list(type))')
    def test_create_list_list_unicode(self):
        def test_impl():
            S = pd.Series([
                          ['abc', 'defg', 'ijk'],
                          ['lmn', 'opq', 'rstuvwxyz']
                          ])
            return S
        hpat_func = hpat.jit(test_impl)

        result_ref = test_impl()
        result = hpat_func()
        pd.testing.assert_series_equal(result, result_ref)

    @unittest.skip('Feature request: implement Series::ctor with list(list(type))')
    def test_create_list_list_integer(self):
        def test_impl():
            S = pd.Series([
                          [123, 456, -789],
                          [-112233, 445566, 778899]
                          ])
            return S
        hpat_func = hpat.jit(test_impl)

        result_ref = test_impl()
        result = hpat_func()
        pd.testing.assert_series_equal(result, result_ref)

    @unittest.skip('Feature request: implement Series::ctor with list(list(type))')
    def test_create_list_list_float(self):
        def test_impl():
            S = pd.Series([
                          [1.23, -4.56, 7.89],
                          [11.2233, 44.5566, -778.899]
                          ])
            return S
        hpat_func = hpat.jit(test_impl)

        result_ref = test_impl()
        result = hpat_func()
        pd.testing.assert_series_equal(result, result_ref)

    def test_create2(self):
        def test_impl(n):
            df = pd.DataFrame({'A': np.arange(n)})
            return (df.A == 2).sum()
        hpat_func = hpat.jit(test_impl)

        n = 11
        self.assertEqual(hpat_func(n), test_impl(n))

    def test_create_series1(self):
        def test_impl():
            A = pd.Series([1, 2, 3])
            return A
        hpat_func = hpat.jit(test_impl)

        pd.testing.assert_series_equal(hpat_func(), test_impl())

    def test_create_series_index1(self):
        # create and box an indexed Series
        def test_impl():
            A = pd.Series([1, 2, 3], ['A', 'C', 'B'])
            return A
        hpat_func = hpat.jit(test_impl)

        pd.testing.assert_series_equal(hpat_func(), test_impl())

    def test_create_series_index2(self):
        def test_impl():
            A = pd.Series([1, 2, 3], index=['A', 'C', 'B'])
            return A
        hpat_func = hpat.jit(test_impl)

        pd.testing.assert_series_equal(hpat_func(), test_impl())

    def test_create_series_index3(self):
        def test_impl():
            A = pd.Series([1, 2, 3], index=['A', 'C', 'B'], name='A')
            return A
        hpat_func = hpat.jit(test_impl)

        pd.testing.assert_series_equal(hpat_func(), test_impl())

    def test_create_series_index4(self):
        def test_impl(name):
            A = pd.Series([1, 2, 3], index=['A', 'C', 'B'], name=name)
            return A
        hpat_func = hpat.jit(test_impl)

        pd.testing.assert_series_equal(hpat_func('A'), test_impl('A'))

    def test_create_str(self):
        def test_impl():
            df = pd.DataFrame({'A': ['a', 'b', 'c']})
            return (df.A == 'a').sum()
        hpat_func = hpat.jit(test_impl)

        self.assertEqual(hpat_func(), test_impl())

    def test_pass_df1(self):
        def test_impl(df):
            return (df.A == 2).sum()
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        self.assertEqual(hpat_func(df), test_impl(df))

    def test_pass_df_str(self):
        def test_impl(df):
            return (df.A == 'a').sum()
        hpat_func = hpat.jit(test_impl)

        df = pd.DataFrame({'A': ['a', 'b', 'c']})
        self.assertEqual(hpat_func(df), test_impl(df))

    def test_pass_series1(self):
        # TODO: check to make sure it is series type
        def test_impl(A):
            return (A == 2).sum()
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        self.assertEqual(hpat_func(df.A), test_impl(df.A))

    def test_pass_series2(self):
        # test creating dataframe from passed series
        def test_impl(A):
            df = pd.DataFrame({'A': A})
            return (df.A == 2).sum()
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        self.assertEqual(hpat_func(df.A), test_impl(df.A))

    def test_pass_series_str(self):
        def test_impl(A):
            return (A == 'a').sum()
        hpat_func = hpat.jit(test_impl)

        df = pd.DataFrame({'A': ['a', 'b', 'c']})
        self.assertEqual(hpat_func(df.A), test_impl(df.A))

    def test_pass_series_index1(self):
        def test_impl(A):
            return A
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([3, 5, 6], ['a', 'b', 'c'], name='A')
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_size(self):
        def test_impl(S):
            return S.size
        hpat_func = hpat.jit(test_impl)

        n = 11
        for S, expected in [
            (pd.Series(), 0),
            (pd.Series([]), 0),
            (pd.Series(np.arange(n)), n),
            (pd.Series([np.nan, 1, 2]), 3),
            (pd.Series(['1', '2', '3']), 3),
        ]:
            with self.subTest(S=S, expected=expected):
                self.assertEqual(hpat_func(S), expected)
                self.assertEqual(hpat_func(S), test_impl(S))

    def test_series_attr2(self):
        def test_impl(A):
            return A.copy().values
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        np.testing.assert_array_equal(hpat_func(df.A), test_impl(df.A))

    def test_series_attr3(self):
        def test_impl(A):
            return A.min()
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        self.assertEqual(hpat_func(df.A), test_impl(df.A))

    def test_series_attr4(self):
        def test_impl(A):
            return A.cumsum().values
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        np.testing.assert_array_equal(hpat_func(df.A), test_impl(df.A))

    def test_series_argsort1(self):
        def test_impl(A):
            return A.argsort()
        hpat_func = hpat.jit(test_impl)

        n = 11
        A = pd.Series(np.random.ranf(n))
        pd.testing.assert_series_equal(hpat_func(A), test_impl(A))

    def test_series_attr6(self):
        def test_impl(A):
            return A.take([2, 3]).values
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        np.testing.assert_array_equal(hpat_func(df.A), test_impl(df.A))

    def test_series_attr7(self):
        def test_impl(A):
            return A.astype(np.float64)
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        np.testing.assert_array_equal(hpat_func(df.A), test_impl(df.A))

    def test_series_getattr_ndim(self):
        '''Verifies getting Series attribute ndim is supported'''
        def test_impl(S):
            return S.ndim
        hpat_func = hpat.jit(test_impl)

        n = 11
        S = pd.Series(np.arange(n))
        self.assertEqual(hpat_func(S), test_impl(S))

    def test_series_getattr_T(self):
        '''Verifies getting Series attribute T is supported'''
        def test_impl(S):
            return S.T
        hpat_func = hpat.jit(test_impl)

        n = 11
        S = pd.Series(np.arange(n))
        np.testing.assert_array_equal(hpat_func(S), test_impl(S))

    def test_series_copy_str1(self):
        def test_impl(A):
            return A.copy()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series(['aa', 'bb', 'cc'])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_copy_int1(self):
        def test_impl(A):
            return A.copy()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([1, 2, 3])
        np.testing.assert_array_equal(hpat_func(S), test_impl(S))

    def test_series_copy_deep(self):
        def test_impl(A, deep):
            return A.copy(deep=deep)
        hpat_func = hpat.jit(test_impl)

        for S in [
            pd.Series([1, 2]),
            pd.Series([1, 2], index=["a", "b"]),
        ]:
            with self.subTest(S=S):
                for deep in (True, False):
                    with self.subTest(deep=deep):
                        actual = hpat_func(S, deep)
                        expected = test_impl(S, deep)

                        pd.testing.assert_series_equal(actual, expected)

                        self.assertEqual(actual.values is S.values, expected.values is S.values)
                        self.assertEqual(actual.values is S.values, not deep)

                        # Shallow copy of index is not supported yet
                        if deep:
                            self.assertEqual(actual.index is S.index, expected.index is S.index)
                            self.assertEqual(actual.index is S.index, not deep)

    def test_series_astype_int_to_str1(self):
        '''Verifies Series.astype implementation with function 'str' as argument
           converts integer series to series of strings
        '''
        def test_impl(S):
            return S.astype(str)
        hpat_func = hpat.jit(test_impl)

        n = 11
        S = pd.Series(np.arange(n))
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_astype_int_to_str2(self):
        '''Verifies Series.astype implementation with a string literal dtype argument
           converts integer series to series of strings
        '''
        def test_impl(S):
            return S.astype('str')
        hpat_func = hpat.jit(test_impl)

        n = 11
        S = pd.Series(np.arange(n))
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_astype_str_to_str1(self):
        '''Verifies Series.astype implementation with function 'str' as argument
           handles string series not changing it
        '''
        def test_impl(S):
            return S.astype(str)
        hpat_func = hpat.jit(test_impl)

        S = pd.Series(['aa', 'bb', 'cc'])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_astype_str_to_str2(self):
        '''Verifies Series.astype implementation with a string literal dtype argument
           handles string series not changing it
        '''
        def test_impl(S):
            return S.astype('str')
        hpat_func = hpat.jit(test_impl)

        S = pd.Series(['aa', 'bb', 'cc'])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_astype_str_to_str_index_str(self):
        '''Verifies Series.astype implementation with function 'str' as argument
           handles string series not changing it
        '''

        def test_impl(S):
            return S.astype(str)

        hpat_func = hpat.jit(test_impl)

        S = pd.Series(['aa', 'bb', 'cc'], index=['d', 'e', 'f'])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_astype_str_to_str_index_int(self):
        '''Verifies Series.astype implementation with function 'str' as argument
           handles string series not changing it
        '''

        def test_impl(S):
            return S.astype(str)

        hpat_func = hpat.jit(test_impl)

        S = pd.Series(['aa', 'bb', 'cc'], index=[1, 2, 3])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    @unittest.skip('TODO: requires str(datetime64) support in Numba')
    def test_series_astype_dt_to_str1(self):
        '''Verifies Series.astype implementation with function 'str' as argument
           converts datetime series to series of strings
        '''
        def test_impl(A):
            return A.astype(str)
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([pd.Timestamp('20130101 09:00:00'),
                       pd.Timestamp('20130101 09:00:02'),
                       pd.Timestamp('20130101 09:00:03')
                       ])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    @unittest.skip('AssertionError: Series are different'
                   '[left]:  [0.000000, 1.000000, 2.000000, 3.000000, ...'
                   '[right]:  [0.0, 1.0, 2.0, 3.0, ...'
                   'TODO: needs alignment to NumPy on Numba side')
    def test_series_astype_float_to_str1(self):
        '''Verifies Series.astype implementation with function 'str' as argument
           converts float series to series of strings
        '''
        def test_impl(A):
            return A.astype(str)
        hpat_func = hpat.jit(test_impl)

        n = 11.0
        S = pd.Series(np.arange(n))
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_astype_int32_to_int64(self):
        '''Verifies Series.astype implementation with NumPy dtype argument
           converts series with dtype=int32 to series with dtype=int64
        '''
        def test_impl(A):
            return A.astype(np.int64)
        hpat_func = hpat.jit(test_impl)

        n = 11
        S = pd.Series(np.arange(n), dtype=np.int32)
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_astype_int_to_float64(self):
        '''Verifies Series.astype implementation with NumPy dtype argument
           converts integer series to series of float
        '''
        def test_impl(A):
            return A.astype(np.float64)
        hpat_func = hpat.jit(test_impl)

        n = 11
        S = pd.Series(np.arange(n))
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_astype_float_to_int32(self):
        '''Verifies Series.astype implementation with NumPy dtype argument
           converts float series to series of integers
        '''
        def test_impl(A):
            return A.astype(np.int32)
        hpat_func = hpat.jit(test_impl)

        n = 11.0
        S = pd.Series(np.arange(n))
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    @unittest.skip('TODO: needs Numba astype impl support string literal as dtype arg')
    def test_series_astype_literal_dtype1(self):
        '''Verifies Series.astype implementation with a string literal dtype argument
           converts float series to series of integers
        '''
        def test_impl(A):
            return A.astype('int32')
        hpat_func = hpat.jit(test_impl)

        n = 11.0
        S = pd.Series(np.arange(n))
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    @unittest.skip('TODO: needs Numba astype impl support converting unicode_type to int')
    def test_series_astype_str_to_int32(self):
        '''Verifies Series.astype implementation with NumPy dtype argument
           converts series of strings to series of integers
        '''
        import numba

        def test_impl(A):
            return A.astype(np.int32)
        hpat_func = hpat.jit(test_impl)

        n = 11
        S = pd.Series([str(x) for x in np.arange(n) - n // 2])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    @unittest.skip('TODO: needs Numba astype impl support converting unicode_type to float')
    def test_series_astype_str_to_float64(self):
        '''Verifies Series.astype implementation with NumPy dtype argument
           converts series of strings to series of float
        '''
        def test_impl(A):
            return A.astype(np.float64)
        hpat_func = hpat.jit(test_impl)

        S = pd.Series(['3.24', '1E+05', '-1', '-1.3E-01', 'nan', 'inf'])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_astype_str_index_str(self):
        '''Verifies Series.astype implementation with function 'str' as argument
           handles string series not changing it
        '''

        def test_impl(S):
            return S.astype(str)
        hpat_func = hpat.jit(test_impl)

        S = pd.Series(['aa', 'bb', 'cc'], index=['a', 'b', 'c'])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_astype_str_index_int(self):
        '''Verifies Series.astype implementation with function 'str' as argument
           handles string series not changing it
        '''

        def test_impl(S):
            return S.astype(str)

        hpat_func = hpat.jit(test_impl)

        S = pd.Series(['aa', 'bb', 'cc'], index=[2, 3, 5])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_np_call_on_series1(self):
        def test_impl(A):
            return np.min(A)
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        np.testing.assert_array_equal(hpat_func(df.A), test_impl(df.A))

    def test_series_values(self):
        def test_impl(A):
            return A.values
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        np.testing.assert_array_equal(hpat_func(df.A), test_impl(df.A))

    def test_series_values1(self):
        def test_impl(A):
            return (A == 2).values
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        np.testing.assert_array_equal(hpat_func(df.A), test_impl(df.A))

    def test_series_shape1(self):
        def test_impl(A):
            return A.shape
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        self.assertEqual(hpat_func(df.A), test_impl(df.A))

    def test_static_setitem_series1(self):
        def test_impl(A):
            A[0] = 2
            return (A == 2).sum()
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        self.assertEqual(hpat_func(df.A), test_impl(df.A))

    def test_setitem_series1(self):
        def test_impl(A, i):
            A[i] = 2
            return (A == 2).sum()
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        self.assertEqual(hpat_func(df.A.copy(), 0), test_impl(df.A.copy(), 0))

    def test_setitem_series2(self):
        def test_impl(A, i):
            A[i] = 100
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        A1 = df.A.copy()
        A2 = df.A
        hpat_func(A1, 0)
        test_impl(A2, 0)
        pd.testing.assert_series_equal(A1, A2)

    @unittest.skip("enable after remove dead in hiframes is removed")
    def test_setitem_series3(self):
        def test_impl(A, i):
            S = pd.Series(A)
            S[i] = 100
        hpat_func = hpat.jit(test_impl)

        n = 11
        A = np.arange(n)
        A1 = A.copy()
        A2 = A
        hpat_func(A1, 0)
        test_impl(A2, 0)
        np.testing.assert_array_equal(A1, A2)

    def test_setitem_series_bool1(self):
        def test_impl(A):
            A[A > 3] = 100
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        A1 = df.A.copy()
        A2 = df.A
        hpat_func(A1)
        test_impl(A2)
        pd.testing.assert_series_equal(A1, A2)

    def test_setitem_series_bool2(self):
        def test_impl(A, B):
            A[A > 3] = B[A > 3]
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n), 'B': np.arange(n)**2})
        A1 = df.A.copy()
        A2 = df.A
        hpat_func(A1, df.B)
        test_impl(A2, df.B)
        pd.testing.assert_series_equal(A1, A2)

    def test_static_getitem_series1(self):
        def test_impl(A):
            return A[0]
        hpat_func = hpat.jit(test_impl)

        n = 11
        A = pd.Series(np.arange(n))
        self.assertEqual(hpat_func(A), test_impl(A))

    def test_getitem_series1(self):
        def test_impl(A, i):
            return A[i]
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        self.assertEqual(hpat_func(df.A, 0), test_impl(df.A, 0))

    def test_getitem_series_str1(self):
        def test_impl(A, i):
            return A[i]
        hpat_func = hpat.jit(test_impl)

        df = pd.DataFrame({'A': ['aa', 'bb', 'cc']})
        self.assertEqual(hpat_func(df.A, 0), test_impl(df.A, 0))

    def test_series_iat1(self):
        def test_impl(A):
            return A.iat[3]
        hpat_func = hpat.jit(test_impl)

        n = 11
        S = pd.Series(np.arange(n)**2)
        self.assertEqual(hpat_func(S), test_impl(S))

    def test_series_iat2(self):
        def test_impl(A):
            A.iat[3] = 1
            return A
        hpat_func = hpat.jit(test_impl)

        n = 11
        S = pd.Series(np.arange(n)**2)
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_iloc1(self):
        def test_impl(A):
            return A.iloc[3]
        hpat_func = hpat.jit(test_impl)

        n = 11
        S = pd.Series(np.arange(n)**2)
        self.assertEqual(hpat_func(S), test_impl(S))

    def test_series_iloc2(self):
        def test_impl(A):
            return A.iloc[3:8]
        hpat_func = hpat.jit(test_impl)

        n = 11
        S = pd.Series(np.arange(n)**2)
        pd.testing.assert_series_equal(
            hpat_func(S), test_impl(S).reset_index(drop=True))

    def test_series_op1(self):
        arithmetic_binops = ('+', '-', '*', '/', '//', '%', '**')
        for operator in arithmetic_binops:
            test_impl = _make_func_use_binop1(operator)
            hpat_func = hpat.jit(test_impl)

            n = 11
            df = pd.DataFrame({'A': np.arange(1, n), 'B': np.ones(n - 1)})
            pd.testing.assert_series_equal(hpat_func(df.A, df.B), test_impl(df.A, df.B), check_names=False)

    def test_series_op2(self):
        arithmetic_binops = ('+', '-', '*', '/', '//', '%', '**')

        for operator in arithmetic_binops:
            test_impl = _make_func_use_binop1(operator)
            hpat_func = hpat.jit(test_impl)

            n = 11
            if platform.system() == 'Windows' and not IS_32BITS:
                df = pd.DataFrame({'A': np.arange(1, n, dtype=np.int64)})
            else:
                df = pd.DataFrame({'A': np.arange(1, n)})
            pd.testing.assert_series_equal(hpat_func(df.A, 1), test_impl(df.A, 1), check_names=False)

    def test_series_op3(self):
        arithmetic_binops = ('+', '-', '*', '/', '//', '%', '**')

        for operator in arithmetic_binops:
            test_impl = _make_func_use_binop2(operator)
            hpat_func = hpat.jit(test_impl)

            n = 11
            df = pd.DataFrame({'A': np.arange(1, n), 'B': np.ones(n - 1)})
            pd.testing.assert_series_equal(hpat_func(df.A, df.B), test_impl(df.A, df.B), check_names=False)

    def test_series_op4(self):
        arithmetic_binops = ('+', '-', '*', '/', '//', '%', '**')

        for operator in arithmetic_binops:
            test_impl = _make_func_use_binop2(operator)
            hpat_func = hpat.jit(test_impl)

            n = 11
            df = pd.DataFrame({'A': np.arange(1, n)})
            pd.testing.assert_series_equal(hpat_func(df.A, 1), test_impl(df.A, 1), check_names=False)

    def test_series_op5(self):
        arithmetic_methods = ('add', 'sub', 'mul', 'div', 'truediv', 'floordiv', 'mod', 'pow')

        for method in arithmetic_methods:
            test_impl = _make_func_use_method_arg1(method)
            hpat_func = hpat.jit(test_impl)

            n = 11
            df = pd.DataFrame({'A': np.arange(1, n), 'B': np.ones(n - 1)})
            pd.testing.assert_series_equal(hpat_func(df.A, df.B), test_impl(df.A, df.B), check_names=False)

    @unittest.skipIf(platform.system() == 'Windows', 'Series values are different (20.0 %)'
                     '[left]:  [1, 1024, 59049, 1048576, 9765625, 60466176, 282475249, 1073741824, 3486784401, 10000000000]'
                     '[right]: [1, 1024, 59049, 1048576, 9765625, 60466176, 282475249, 1073741824, -808182895, 1410065408]')
    def test_series_op5_integer_scalar(self):
        arithmetic_methods = ('add', 'sub', 'mul', 'div', 'truediv', 'floordiv', 'mod', 'pow')

        for method in arithmetic_methods:
            test_impl = _make_func_use_method_arg1(method)
            hpat_func = hpat.jit(test_impl)

            n = 11
            if platform.system() == 'Windows' and not IS_32BITS:
                operand_series = pd.Series(np.arange(1, n, dtype=np.int64))
            else:
                operand_series = pd.Series(np.arange(1, n))
            operand_scalar = 10
            pd.testing.assert_series_equal(
                hpat_func(operand_series, operand_scalar),
                test_impl(operand_series, operand_scalar),
                check_names=False)

    def test_series_op5_float_scalar(self):
        arithmetic_methods = ('add', 'sub', 'mul', 'div', 'truediv', 'floordiv', 'mod', 'pow')

        for method in arithmetic_methods:
            test_impl = _make_func_use_method_arg1(method)
            hpat_func = hpat.jit(test_impl)

            n = 11
            operand_series = pd.Series(np.arange(1, n))
            operand_scalar = .5
            pd.testing.assert_series_equal(
                hpat_func(operand_series, operand_scalar),
                test_impl(operand_series, operand_scalar),
                check_names=False)

    def test_series_op6(self):
        def test_impl(A):
            return -A
        hpat_func = hpat.jit(test_impl)

        n = 11
        A = pd.Series(np.arange(n))
        pd.testing.assert_series_equal(hpat_func(A), test_impl(A))

    def test_series_op7(self):
        comparison_binops = ('<', '>', '<=', '>=', '!=', '==')

        for operator in comparison_binops:
            test_impl = _make_func_use_binop1(operator)
            hpat_func = hpat.jit(test_impl)

            n = 11
            A = pd.Series(np.arange(n))
            B = pd.Series(np.arange(n)**2)
            pd.testing.assert_series_equal(hpat_func(A, B), test_impl(A, B), check_names=False)

    def test_series_op8(self):
        comparison_methods = ('lt', 'gt', 'le', 'ge', 'ne', 'eq')

        for method in comparison_methods:
            test_impl = _make_func_use_method_arg1(method)
            hpat_func = hpat.jit(test_impl)

            n = 11
            A = pd.Series(np.arange(n))
            B = pd.Series(np.arange(n)**2)
            pd.testing.assert_series_equal(hpat_func(A, B), test_impl(A, B), check_names=False)

    @unittest.skipIf(platform.system() == 'Windows', "Attribute dtype are different: int64, int32")
    def test_series_op8_integer_scalar(self):
        comparison_methods = ('lt', 'gt', 'le', 'ge', 'eq', 'ne')

        for method in comparison_methods:
            test_impl = _make_func_use_method_arg1(method)
            hpat_func = hpat.jit(test_impl)

            n = 11
            operand_series = pd.Series(np.arange(1, n))
            operand_scalar = 10
            pd.testing.assert_series_equal(
                hpat_func(operand_series, operand_scalar),
                test_impl(operand_series, operand_scalar),
                check_names=False)

    def test_series_op8_float_scalar(self):
        comparison_methods = ('lt', 'gt', 'le', 'ge', 'eq', 'ne')

        for method in comparison_methods:
            test_impl = _make_func_use_method_arg1(method)
            hpat_func = hpat.jit(test_impl)

            n = 11
            operand_series = pd.Series(np.arange(1, n))
            operand_scalar = .5
            pd.testing.assert_series_equal(
                hpat_func(operand_series, operand_scalar),
                test_impl(operand_series, operand_scalar),
                check_names=False)

    def test_series_inplace_binop_array(self):
        def test_impl(A, B):
            A += B
            return A
        hpat_func = hpat.jit(test_impl)

        n = 11
        A = np.arange(n)**2.0  # TODO: use 2 for test int casting
        B = pd.Series(np.ones(n))
        np.testing.assert_array_equal(hpat_func(A.copy(), B), test_impl(A, B))

    def test_series_fusion1(self):
        def test_impl(A, B):
            return A + B + 1
        hpat_func = hpat.jit(test_impl)

        n = 11
        if platform.system() == 'Windows' and not IS_32BITS:
            A = pd.Series(np.arange(n), dtype=np.int64)
            B = pd.Series(np.arange(n)**2, dtype=np.int64)
        else:
            A = pd.Series(np.arange(n))
            B = pd.Series(np.arange(n)**2)
        pd.testing.assert_series_equal(hpat_func(A, B), test_impl(A, B))
        self.assertEqual(count_parfor_REPs(), 1)

    def test_series_fusion2(self):
        # make sure getting data var avoids incorrect single def assumption
        def test_impl(A, B):
            S = B + 2
            if A[0] == 0:
                S = A + 1
            return S + B
        hpat_func = hpat.jit(test_impl)

        n = 11
        if platform.system() == 'Windows' and not IS_32BITS:
            A = pd.Series(np.arange(n), dtype=np.int64)
            B = pd.Series(np.arange(n)**2, dtype=np.int64)
        else:
            A = pd.Series(np.arange(n))
            B = pd.Series(np.arange(n)**2)
        pd.testing.assert_series_equal(hpat_func(A, B), test_impl(A, B))
        self.assertEqual(count_parfor_REPs(), 3)

    def test_series_len(self):
        def test_impl(A, i):
            return len(A)
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        self.assertEqual(hpat_func(df.A, 0), test_impl(df.A, 0))

    def test_series_box(self):
        def test_impl():
            A = pd.Series([1, 2, 3])
            return A
        hpat_func = hpat.jit(test_impl)

        pd.testing.assert_series_equal(hpat_func(), test_impl())

    def test_series_box2(self):
        def test_impl():
            A = pd.Series(['1', '2', '3'])
            return A
        hpat_func = hpat.jit(test_impl)

        pd.testing.assert_series_equal(hpat_func(), test_impl())

    def test_series_list_str_unbox1(self):
        def test_impl(A):
            return A.iloc[0]
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([['aa', 'b'], ['ccc'], []])
        np.testing.assert_array_equal(hpat_func(S), test_impl(S))

        # call twice to test potential refcount errors
        np.testing.assert_array_equal(hpat_func(S), test_impl(S))

    def test_np_typ_call_replace(self):
        # calltype replacement is tricky for np.typ() calls since variable
        # type can't provide calltype
        def test_impl(i):
            return np.int32(i)
        hpat_func = hpat.jit(test_impl)

        self.assertEqual(hpat_func(1), test_impl(1))

    def test_series_ufunc1(self):
        def test_impl(A, i):
            return np.isinf(A).values
        hpat_func = hpat.jit(test_impl)

        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        np.testing.assert_array_equal(hpat_func(df.A, 1), test_impl(df.A, 1))

    def test_list_convert(self):
        def test_impl():
            df = pd.DataFrame({'one': np.array([-1, np.nan, 2.5]),
                               'two': ['foo', 'bar', 'baz'],
                               'three': [True, False, True]})
            return df.one.values, df.two.values, df.three.values
        hpat_func = hpat.jit(test_impl)

        one, two, three = hpat_func()
        self.assertTrue(isinstance(one, np.ndarray))
        self.assertTrue(isinstance(two, np.ndarray))
        self.assertTrue(isinstance(three, np.ndarray))

    @unittest.skip("needs empty_like typing fix in npydecl.py")
    def test_series_empty_like(self):
        def test_impl(A):
            return np.empty_like(A)
        hpat_func = hpat.jit(test_impl)
        n = 11
        df = pd.DataFrame({'A': np.arange(n)})
        self.assertTrue(isinstance(hpat_func(df.A), np.ndarray))

    def test_series_fillna1(self):
        def test_impl(A):
            return A.fillna(5.0)
        hpat_func = hpat.jit(test_impl)

        df = pd.DataFrame({'A': [1.0, 2.0, np.nan, 1.0]})
        pd.testing.assert_series_equal(hpat_func(df.A),
                                       test_impl(df.A), check_names=False)

    # test inplace fillna for named numeric series (obtained from DataFrame)
    def test_series_fillna_inplace1(self):
        def test_impl(A):
            A.fillna(5.0, inplace=True)
            return A
        hpat_func = hpat.jit(test_impl)

        df = pd.DataFrame({'A': [1.0, 2.0, np.nan, 1.0]})
        pd.testing.assert_series_equal(hpat_func(df.A),
                                       test_impl(df.A), check_names=False)

    def test_series_fillna_str1(self):
        def test_impl(A):
            return A.fillna("dd")
        hpat_func = hpat.jit(test_impl)

        df = pd.DataFrame({'A': ['aa', 'b', None, 'ccc']})
        pd.testing.assert_series_equal(hpat_func(df.A),
                                       test_impl(df.A), check_names=False)

    def test_series_fillna_str_inplace1(self):
        def test_impl(A):
            A.fillna("dd", inplace=True)
            return A
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series(['aa', 'b', None, 'ccc'])
        S2 = S1.copy()
        pd.testing.assert_series_equal(hpat_func(S1), test_impl(S2))
        # TODO: handle string array reflection
        # hpat_func(S1)
        # test_impl(S2)
        # np.testing.assert_array_equal(S1, S2)

    def test_series_fillna_str_inplace_empty1(self):
        def test_impl(A):
            A.fillna("", inplace=True)
            return A
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series(['aa', 'b', None, 'ccc'])
        S2 = S1.copy()
        pd.testing.assert_series_equal(hpat_func(S1), test_impl(S2))

    @unittest.skip('Unsupported functionality: failed to handle index')
    def test_series_fillna_index_str(self):
        def test_impl(S):
            return S.fillna(5.0)
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([1.0, 2.0, np.nan, 1.0], index=['a', 'b', 'c', 'd'])
        pd.testing.assert_series_equal(hpat_func(S),
                                       test_impl(S), check_names=False)

    @unittest.skip('Unsupported functionality: failed to handle index')
    def test_series_fillna_index_int(self):
        def test_impl(S):
            return S.fillna(5.0)

        hpat_func = hpat.jit(test_impl)

        S = pd.Series([1.0, 2.0, np.nan, 1.0], index=[2, 3, 4, 5])
        pd.testing.assert_series_equal(hpat_func(S),
                                       test_impl(S), check_names=False)

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     'No support of axis argument in old-style Series.dropna() impl')
    def test_series_dropna_axis1(self):
        '''Verifies Series.dropna() implementation handles 'index' as axis argument'''
        def test_impl(S):
            return S.dropna(axis='index')
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([1.0, 2.0, np.nan, 1.0, np.inf])
        S2 = S1.copy()
        pd.testing.assert_series_equal(hpat_func(S1), test_impl(S2))

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     'No support of axis argument in old-style Series.dropna() impl')
    def test_series_dropna_axis2(self):
        '''Verifies Series.dropna() implementation handles 0 as axis argument'''
        def test_impl(S):
            return S.dropna(axis=0)
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([1.0, 2.0, np.nan, 1.0, np.inf])
        S2 = S1.copy()
        pd.testing.assert_series_equal(hpat_func(S1), test_impl(S2))

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     'No support of axis argument in old-style Series.dropna() impl')
    def test_series_dropna_axis3(self):
        '''Verifies Series.dropna() implementation handles correct non-literal axis argument'''
        def test_impl(S, axis):
            return S.dropna(axis=axis)
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([1.0, 2.0, np.nan, 1.0, np.inf])
        S2 = S1.copy()
        axis_values = [0, 'index']
        for value in axis_values:
            pd.testing.assert_series_equal(hpat_func(S1, value), test_impl(S2, value))

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     'BUG: old-style dropna impl returns series without index')
    def test_series_dropna_float_index1(self):
        '''Verifies Series.dropna() implementation for float series with default index'''
        def test_impl(S):
            return S.dropna()
        hpat_func = hpat.jit(test_impl)

        for data in test_global_input_data_float64:
            S1 = pd.Series(data)
            S2 = S1.copy()
            pd.testing.assert_series_equal(hpat_func(S1), test_impl(S2))

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     'BUG: old-style dropna impl returns series without index')
    def test_series_dropna_float_index2(self):
        '''Verifies Series.dropna() implementation for float series with string index'''
        def test_impl(S):
            return S.dropna()
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([1.0, 2.0, np.nan, 1.0, np.inf], ['a', 'b', 'c', 'd', 'e'])
        S2 = S1.copy()
        pd.testing.assert_series_equal(hpat_func(S1), test_impl(S2))

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     'BUG: old-style dropna impl returns series without index')
    def test_series_dropna_str_index1(self):
        '''Verifies Series.dropna() implementation for series of strings with default index'''
        def test_impl(S):
            return S.dropna()
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series(['aa', 'b', None, 'cccd', ''])
        S2 = S1.copy()
        pd.testing.assert_series_equal(hpat_func(S1), test_impl(S2))

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     'BUG: old-style dropna impl returns series without index')
    def test_series_dropna_str_index2(self):
        '''Verifies Series.dropna() implementation for series of strings with string index'''
        def test_impl(S):
            return S.dropna()
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series(['aa', 'b', None, 'cccd', ''], ['a', 'b', 'c', 'd', 'e'])
        S2 = S1.copy()
        pd.testing.assert_series_equal(hpat_func(S1), test_impl(S2))

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     'BUG: old-style dropna impl returns series without index')
    def test_series_dropna_str_index3(self):
        def test_impl(S):
            return S.dropna()

        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series(['aa', 'b', None, 'cccd', ''], index=[1, 2, 5, 7, 10])
        S2 = S1.copy()
        pd.testing.assert_series_equal(hpat_func(S1), test_impl(S2))

    @unittest.skip('BUG: old-style dropna impl returns series without index, in new-style inplace is unsupported')
    def test_series_dropna_float_inplace_no_index1(self):
        '''Verifies Series.dropna() implementation for float series with default index and inplace argument True'''
        def test_impl(S):
            S.dropna(inplace=True)
            return S
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([1.0, 2.0, np.nan, 1.0, np.inf])
        S2 = S1.copy()
        pd.testing.assert_series_equal(hpat_func(S1), test_impl(S2))

    @unittest.skip('TODO: add reflection support and check method return value')
    def test_series_dropna_float_inplace_no_index2(self):
        '''Verifies Series.dropna(inplace=True) results are reflected back in the original float series'''
        def test_impl(S):
            return S.dropna(inplace=True)
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([1.0, 2.0, np.nan, 1.0, np.inf])
        S2 = S1.copy()
        self.assertIsNone(hpat_func(S1))
        self.assertIsNone(test_impl(S2))
        pd.testing.assert_series_equal(S1, S2)

    @unittest.skip('BUG: old-style dropna impl returns series without index, in new-style inplace is unsupported')
    def test_series_dropna_str_inplace_no_index1(self):
        '''Verifies Series.dropna() implementation for series of strings
           with default index and inplace argument True
        '''
        def test_impl(S):
            S.dropna(inplace=True)
            return S
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series(['aa', 'b', None, 'cccd', ''])
        S2 = S1.copy()
        pd.testing.assert_series_equal(hpat_func(S1), test_impl(S2))

    @unittest.skip('TODO: add reflection support and check method return value')
    def test_series_dropna_str_inplace_no_index2(self):
        '''Verifies Series.dropna(inplace=True) results are reflected back in the original string series'''
        def test_impl(S):
            return S.dropna(inplace=True)
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series(['aa', 'b', None, 'cccd', ''])
        S2 = S1.copy()
        self.assertIsNone(hpat_func(S1))
        self.assertIsNone(test_impl(S2))
        pd.testing.assert_series_equal(S1, S2)

    def test_series_dropna_str_parallel1(self):
        '''Verifies Series.dropna() distributed work for series of strings with default index'''
        def test_impl(A):
            B = A.dropna()
            return (B == 'gg').sum()
        hpat_func = hpat.jit(distributed=['A'])(test_impl)

        S1 = pd.Series(['aa', 'b', None, 'ccc', 'dd', 'gg'])
        start, end = get_start_end(len(S1))
        # TODO: gatherv
        self.assertEqual(hpat_func(S1[start:end]), test_impl(S1))
        self.assertEqual(count_array_REPs(), 0)
        self.assertEqual(count_parfor_REPs(), 0)
        self.assertTrue(count_array_OneDs() > 0)

    @unittest.skip('AssertionError: Series are different\n'
                   'Series length are different\n'
                   '[left]:  3, Int64Index([0, 1, 2], dtype=\'int64\')\n'
                   '[right]: 2, Int64Index([1, 2], dtype=\'int64\')')
    def test_series_dropna_dt_no_index1(self):
        '''Verifies Series.dropna() implementation for datetime series with default index'''
        def test_impl(S):
            return S.dropna()
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([pd.NaT, pd.Timestamp('1970-12-01'), pd.Timestamp('2012-07-25')])
        S2 = S1.copy()
        pd.testing.assert_series_equal(hpat_func(S1), test_impl(S2))

    def test_series_dropna_bool_no_index1(self):
        '''Verifies Series.dropna() implementation for bool series with default index'''
        def test_impl(S):
            return S.dropna()
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([True, False, False, True])
        S2 = S1.copy()
        pd.testing.assert_series_equal(hpat_func(S1), test_impl(S2))

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     'BUG: old-style dropna impl returns series without index')
    def test_series_dropna_int_no_index1(self):
        '''Verifies Series.dropna() implementation for integer series with default index'''
        def test_impl(S):
            return S.dropna()
        hpat_func = hpat.jit(test_impl)

        n = 11
        S1 = pd.Series(np.arange(n, dtype=np.int64))
        S2 = S1.copy()
        pd.testing.assert_series_equal(hpat_func(S1), test_impl(S2))

    @unittest.skip('numba.errors.TypingError - fix needed\n'
                   'Failed in hpat mode pipeline'
                   '(step: convert to distributed)\n'
                   'Invalid use of Function(<built-in function len>)'
                   'with argument(s) of type(s): (none)\n')
    def test_series_rename1(self):
        def test_impl(A):
            return A.rename('B')
        hpat_func = hpat.jit(test_impl)

        df = pd.DataFrame({'A': [1.0, 2.0, np.nan, 1.0]})
        pd.testing.assert_series_equal(hpat_func(df.A), test_impl(df.A))

    def test_series_sum_default(self):
        def test_impl(S):
            return S.sum()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([1., 2., 3.])
        self.assertEqual(hpat_func(S), test_impl(S))

    def test_series_sum_nan(self):
        def test_impl(S):
            return S.sum()
        hpat_func = hpat.jit(test_impl)

        # column with NA
        S = pd.Series([np.nan, 2., 3.])
        self.assertEqual(hpat_func(S), test_impl(S))

        # all NA case should produce 0
        S = pd.Series([np.nan, np.nan])
        self.assertEqual(hpat_func(S), test_impl(S))

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default, "Old style Series.sum() does not support parameters")
    def test_series_sum_skipna_false(self):
        def test_impl(S):
            return S.sum(skipna=False)
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([np.nan, 2., 3.])
        self.assertEqual(np.isnan(hpat_func(S)), np.isnan(test_impl(S)))

    @unittest.skipIf(not hpat.config.config_pipeline_hpat_default,
                     "Series.sum() operator + is not implemented yet for Numba")
    def test_series_sum2(self):
        def test_impl(S):
            return (S + S).sum()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([np.nan, 2., 3.])
        self.assertEqual(hpat_func(S), test_impl(S))

        S = pd.Series([np.nan, np.nan])
        self.assertEqual(hpat_func(S), test_impl(S))

    def test_series_prod(self):
        def test_impl(S, skipna):
            return S.prod(skipna=skipna)
        hpat_func = hpat.jit(test_impl)

        data_samples = [
            [6, 6, 2, 1, 3, 3, 2, 1, 2],
            [1.1, 0.3, 2.1, 1, 3, 0.3, 2.1, 1.1, 2.2],
            [6, 6.1, 2.2, 1, 3, 3, 2.2, 1, 2],
            [6, 6, np.nan, 2, np.nan, 1, 3, 3, np.inf, 2, 1, 2, np.inf],
            [1.1, 0.3, np.nan, 1.0, np.inf, 0.3, 2.1, np.nan, 2.2, np.inf],
            [1.1, 0.3, np.nan, 1, np.inf, 0, 1.1, np.nan, 2.2, np.inf, 2, 2],
            [np.nan, np.nan, np.nan],
            [np.nan, np.nan, np.inf],
        ]

        for data in data_samples:
            S = pd.Series(data)

            for skipna_var in [True, False]:
                actual = hpat_func(S, skipna=skipna_var)
                expected = test_impl(S, skipna=skipna_var)

                if np.isnan(actual) or np.isnan(expected):
                    # con not compare Nan != Nan directly
                    self.assertEqual(np.isnan(actual), np.isnan(expected))
                else:
                    self.assertEqual(actual, expected)

    def test_series_prod_skipna_default(self):
        def test_impl(S):
            return S.prod()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([np.nan, 2, 3.])
        self.assertEqual(hpat_func(S), test_impl(S))

    def test_series_count1(self):
        def test_impl(S):
            return S.count()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([np.nan, 2., 3.])
        self.assertEqual(hpat_func(S), test_impl(S))

        S = pd.Series([np.nan, np.nan])
        self.assertEqual(hpat_func(S), test_impl(S))

        S = pd.Series(['aa', 'bb', np.nan])
        self.assertEqual(hpat_func(S), test_impl(S))

    def test_series_mean(self):
        def test_impl(S):
            return S.mean()
        hpat_func = hpat.jit(test_impl)

        data_samples = [
            [6, 6, 2, 1, 3, 3, 2, 1, 2],
            [1.1, 0.3, 2.1, 1, 3, 0.3, 2.1, 1.1, 2.2],
            [6, 6.1, 2.2, 1, 3, 3, 2.2, 1, 2],
            [6, 6, np.nan, 2, np.nan, 1, 3, 3, np.inf, 2, 1, 2, np.inf],
            [1.1, 0.3, np.nan, 1.0, np.inf, 0.3, 2.1, np.nan, 2.2, np.inf],
            [1.1, 0.3, np.nan, 1, np.inf, 0, 1.1, np.nan, 2.2, np.inf, 2, 2],
            [np.nan, np.nan, np.nan],
            [np.nan, np.nan, np.inf],
        ]

        for data in data_samples:
            with self.subTest(data=data):
                S = pd.Series(data)
                actual = hpat_func(S)
                expected = test_impl(S)
                if np.isnan(actual) or np.isnan(expected):
                    self.assertEqual(np.isnan(actual), np.isnan(expected))
                else:
                    self.assertEqual(actual, expected)

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default, "Series.mean() any parameters unsupported")
    def test_series_mean_skipna(self):
        def test_impl(S, skipna):
            return S.mean(skipna=skipna)
        hpat_func = hpat.jit(test_impl)

        data_samples = [
            [6, 6, 2, 1, 3, 3, 2, 1, 2],
            [1.1, 0.3, 2.1, 1, 3, 0.3, 2.1, 1.1, 2.2],
            [6, 6.1, 2.2, 1, 3, 3, 2.2, 1, 2],
            [6, 6, np.nan, 2, np.nan, 1, 3, 3, np.inf, 2, 1, 2, np.inf],
            [1.1, 0.3, np.nan, 1.0, np.inf, 0.3, 2.1, np.nan, 2.2, np.inf],
            [1.1, 0.3, np.nan, 1, np.inf, 0, 1.1, np.nan, 2.2, np.inf, 2, 2],
            [np.nan, np.nan, np.nan],
            [np.nan, np.nan, np.inf],
        ]

        for skipna in [True, False]:
            for data in data_samples:
                S = pd.Series(data)
                actual = hpat_func(S, skipna)
                expected = test_impl(S, skipna)
                if np.isnan(actual) or np.isnan(expected):
                    self.assertEqual(np.isnan(actual), np.isnan(expected))
                else:
                    self.assertEqual(actual, expected)

    def test_series_var1(self):
        def test_impl(S):
            return S.var()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([np.nan, 2., 3.])
        self.assertEqual(hpat_func(S), test_impl(S))

    def test_series_min(self):
        def test_impl(S):
            return S.min()
        hpat_func = hpat.jit(test_impl)

        # TODO type_min/type_max
        for input_data in [[np.nan, 2., np.nan, 3., np.inf, 1, -1000],
                           [8, 31, 1123, -1024],
                           [2., 3., 1, -1000, np.inf]]:
            S = pd.Series(input_data)

            result_ref = test_impl(S)
            result = hpat_func(S)
            self.assertEqual(result, result_ref)

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default, "Series.min() any parameters unsupported")
    def test_series_min_param(self):
        def test_impl(S, param_skipna):
            return S.min(skipna=param_skipna)

        hpat_func = hpat.jit(test_impl)

        for input_data, param_skipna in [([np.nan, 2., np.nan, 3., 1, -1000, np.inf], True),
                                         ([2., 3., 1, np.inf, -1000], False)]:
            S = pd.Series(input_data)

            result_ref = test_impl(S, param_skipna)
            result = hpat_func(S, param_skipna)
            self.assertEqual(result, result_ref)

    def test_series_max(self):
        def test_impl(S):
            return S.max()
        hpat_func = hpat.jit(test_impl)

        # TODO type_min/type_max
        for input_data in [[np.nan, 2., np.nan, 3., np.inf, 1, -1000],
                           [8, 31, 1123, -1024],
                           [2., 3., 1, -1000, np.inf]]:
            S = pd.Series(input_data)

            result_ref = test_impl(S)
            result = hpat_func(S)
            self.assertEqual(result, result_ref)

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default, "Series.max() any parameters unsupported")
    def test_series_max_param(self):
        def test_impl(S, param_skipna):
            return S.max(skipna=param_skipna)

        hpat_func = hpat.jit(test_impl)

        for input_data, param_skipna in [([np.nan, 2., np.nan, 3., 1, -1000, np.inf], True),
                                         ([2., 3., 1, np.inf, -1000], False)]:
            S = pd.Series(input_data)

            result_ref = test_impl(S, param_skipna)
            result = hpat_func(S, param_skipna)
            self.assertEqual(result, result_ref)

    def test_series_value_counts(self):
        def test_impl(S):
            return S.value_counts()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series(['AA', 'BB', 'C', 'AA', 'C', 'AA'])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_dist_input1(self):
        '''Verify distribution of a Series without index'''
        def test_impl(S):
            return S.max()
        hpat_func = hpat.jit(distributed={'S'})(test_impl)

        n = 111
        S = pd.Series(np.arange(n))
        start, end = get_start_end(n)
        self.assertEqual(hpat_func(S[start:end]), test_impl(S))
        self.assertEqual(count_array_REPs(), 0)
        self.assertEqual(count_parfor_REPs(), 0)

    def test_series_dist_input2(self):
        '''Verify distribution of a Series with integer index'''
        def test_impl(S):
            return S.max()
        hpat_func = hpat.jit(distributed={'S'})(test_impl)

        n = 111
        S = pd.Series(np.arange(n), 1 + np.arange(n))
        start, end = get_start_end(n)
        self.assertEqual(hpat_func(S[start:end]), test_impl(S))
        self.assertEqual(count_array_REPs(), 0)
        self.assertEqual(count_parfor_REPs(), 0)

    @unittest.skip("Passed if run single")
    def test_series_dist_input3(self):
        '''Verify distribution of a Series with string index'''
        def test_impl(S):
            return S.max()
        hpat_func = hpat.jit(distributed={'S'})(test_impl)

        n = 111
        S = pd.Series(np.arange(n), ['abc{}'.format(id) for id in range(n)])
        start, end = get_start_end(n)
        self.assertEqual(hpat_func(S[start:end]), test_impl(S))
        self.assertEqual(count_array_REPs(), 0)
        self.assertEqual(count_parfor_REPs(), 0)

    def test_series_tuple_input1(self):
        def test_impl(s_tup):
            return s_tup[0].max()
        hpat_func = hpat.jit(test_impl)

        n = 111
        S = pd.Series(np.arange(n))
        S2 = pd.Series(np.arange(n) + 1.0)
        s_tup = (S, 1, S2)
        self.assertEqual(hpat_func(s_tup), test_impl(s_tup))

    @unittest.skip("pending handling of build_tuple in dist pass")
    def test_series_tuple_input_dist1(self):
        def test_impl(s_tup):
            return s_tup[0].max()
        hpat_func = hpat.jit(locals={'s_tup:input': 'distributed'})(test_impl)

        n = 111
        S = pd.Series(np.arange(n))
        S2 = pd.Series(np.arange(n) + 1.0)
        start, end = get_start_end(n)
        s_tup = (S, 1, S2)
        h_s_tup = (S[start:end], 1, S2[start:end])
        self.assertEqual(hpat_func(h_s_tup), test_impl(s_tup))

    def test_series_rolling1(self):
        def test_impl(S):
            return S.rolling(3).sum()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([1.0, 2., 3., 4., 5.])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_concat1(self):
        def test_impl(S1, S2):
            return pd.concat([S1, S2]).values
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([1.0, 2., 3., 4., 5.])
        S2 = pd.Series([6., 7.])
        np.testing.assert_array_equal(hpat_func(S1, S2), test_impl(S1, S2))

    def test_series_map1(self):
        def test_impl(S):
            return S.map(lambda a: 2 * a)
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([1.0, 2., 3., 4., 5.])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_map_global1(self):
        def test_impl(S):
            return S.map(lambda a: a + GLOBAL_VAL)
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([1.0, 2., 3., 4., 5.])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_map_tup1(self):
        def test_impl(S):
            return S.map(lambda a: (a, 2 * a))
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([1.0, 2., 3., 4., 5.])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_map_tup_map1(self):
        def test_impl(S):
            A = S.map(lambda a: (a, 2 * a))
            return A.map(lambda a: a[1])
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([1.0, 2., 3., 4., 5.])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_combine(self):
        def test_impl(S1, S2):
            return S1.combine(S2, lambda a, b: 2 * a + b)
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([1.0, 2., 3., 4., 5.])
        S2 = pd.Series([6.0, 21., 3.6, 5.])
        pd.testing.assert_series_equal(hpat_func(S1, S2), test_impl(S1, S2))

    def test_series_combine_float3264(self):
        def test_impl(S1, S2):
            return S1.combine(S2, lambda a, b: 2 * a + b)
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([np.float64(1), np.float64(2),
                        np.float64(3), np.float64(4), np.float64(5)])
        S2 = pd.Series([np.float32(1), np.float32(2),
                        np.float32(3), np.float32(4), np.float32(5)])
        pd.testing.assert_series_equal(hpat_func(S1, S2), test_impl(S1, S2))

    def test_series_combine_assert1(self):
        def test_impl(S1, S2):
            return S1.combine(S2, lambda a, b: 2 * a + b)
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([1, 2, 3])
        S2 = pd.Series([6., 21., 3., 5.])
        with self.assertRaises(AssertionError):
            hpat_func(S1, S2)

    def test_series_combine_assert2(self):
        def test_impl(S1, S2):
            return S1.combine(S2, lambda a, b: 2 * a + b)
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([6., 21., 3., 5.])
        S2 = pd.Series([1, 2, 3])
        with self.assertRaises(AssertionError):
            hpat_func(S1, S2)

    def test_series_combine_integer(self):
        def test_impl(S1, S2):
            return S1.combine(S2, lambda a, b: 2 * a + b, 16)
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([1, 2, 3, 4, 5])
        S2 = pd.Series([6, 21, 3, 5])
        pd.testing.assert_series_equal(hpat_func(S1, S2), test_impl(S1, S2))

    def test_series_combine_different_types(self):
        def test_impl(S1, S2):
            return S1.combine(S2, lambda a, b: 2 * a + b)
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([6.1, 21.2, 3.3, 5.4, 6.7])
        S2 = pd.Series([1, 2, 3, 4, 5])
        pd.testing.assert_series_equal(hpat_func(S1, S2), test_impl(S1, S2))

    def test_series_combine_integer_samelen(self):
        def test_impl(S1, S2):
            return S1.combine(S2, lambda a, b: 2 * a + b)
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([1, 2, 3, 4, 5])
        S2 = pd.Series([6, 21, 17, -5, 4])
        pd.testing.assert_series_equal(hpat_func(S1, S2), test_impl(S1, S2))

    def test_series_combine_samelen(self):
        def test_impl(S1, S2):
            return S1.combine(S2, lambda a, b: 2 * a + b)
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([1.0, 2., 3., 4., 5.])
        S2 = pd.Series([6.0, 21., 3.6, 5., 0.0])
        pd.testing.assert_series_equal(hpat_func(S1, S2), test_impl(S1, S2))

    def test_series_combine_value(self):
        def test_impl(S1, S2):
            return S1.combine(S2, lambda a, b: 2 * a + b, 1237.56)
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([1.0, 2., 3., 4., 5.])
        S2 = pd.Series([6.0, 21., 3.6, 5.])
        pd.testing.assert_series_equal(hpat_func(S1, S2), test_impl(S1, S2))

    def test_series_combine_value_samelen(self):
        def test_impl(S1, S2):
            return S1.combine(S2, lambda a, b: 2 * a + b, 1237.56)
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([1.0, 2., 3., 4., 5.])
        S2 = pd.Series([6.0, 21., 3.6, 5., 0.0])
        pd.testing.assert_series_equal(hpat_func(S1, S2), test_impl(S1, S2))

    def test_series_apply1(self):
        def test_impl(S):
            return S.apply(lambda a: 2 * a)
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([1.0, 2., 3., 4., 5.])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_abs1(self):
        def test_impl(S):
            return S.abs()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([np.nan, -2., 3., 0.5E-01, 0xFF, 0o7, 0b101])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_cov1(self):
        def test_impl(S1, S2):
            return S1.cov(S2)
        hpat_func = hpat.jit(test_impl)

        for pair in _cov_corr_series:
            S1, S2 = pair
            np.testing.assert_almost_equal(
                hpat_func(S1, S2), test_impl(S1, S2),
                err_msg='S1={}\nS2={}'.format(S1, S2))

    def test_series_corr1(self):
        def test_impl(S1, S2):
            return S1.corr(S2)
        hpat_func = hpat.jit(test_impl)

        for pair in _cov_corr_series:
            S1, S2 = pair
            np.testing.assert_almost_equal(
                hpat_func(S1, S2), test_impl(S1, S2),
                err_msg='S1={}\nS2={}'.format(S1, S2))

    def test_series_str_len1(self):
        def test_impl(S):
            return S.str.len()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series(['aa', 'abc', 'c', 'cccd'])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_str2str(self):
        str2str_methods = ('capitalize', 'lower', 'lstrip', 'rstrip',
                           'strip', 'swapcase', 'title', 'upper')
        for method in str2str_methods:
            func_text = "def test_impl(S):\n"
            func_text += "  return S.str.{}()\n".format(method)
            test_impl = _make_func_from_text(func_text)
            hpat_func = hpat.jit(test_impl)

            S = pd.Series([' \tbbCD\t ', 'ABC', ' mCDm\t', 'abc'])
            pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_append1(self):
        def test_impl(S, other):
            return S.append(other).values
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([-2., 3., 9.1])
        S2 = pd.Series([-2., 5.0])
        # Test single series
        np.testing.assert_array_equal(hpat_func(S1, S2), test_impl(S1, S2))

    def test_series_append2(self):
        def test_impl(S1, S2, S3):
            return S1.append([S2, S3]).values
        hpat_func = hpat.jit(test_impl)

        S1 = pd.Series([-2., 3., 9.1])
        S2 = pd.Series([-2., 5.0])
        S3 = pd.Series([1.0])
        # Test series tuple
        np.testing.assert_array_equal(hpat_func(S1, S2, S3),
                                      test_impl(S1, S2, S3))

    def test_series_isin_list1(self):
        def test_impl(S, values):
            return S.isin(values)
        hpat_func = hpat.jit(test_impl)

        n = 11
        S = pd.Series(np.arange(n))
        values = [1, 2, 5, 7, 8]
        pd.testing.assert_series_equal(hpat_func(S, values), test_impl(S, values))

    def test_series_isin_list2(self):
        def test_impl(S, values):
            return S.isin(values)
        hpat_func = hpat.jit(test_impl)

        n = 11.0
        S = pd.Series(np.arange(n))
        values = [1., 2., 5., 7., 8.]
        pd.testing.assert_series_equal(hpat_func(S, values), test_impl(S, values))

    def test_series_isin_list3(self):
        def test_impl(S, values):
            return S.isin(values)
        hpat_func = hpat.jit(test_impl)

        S = pd.Series(['a', 'b', 'q', 'w', 'c', 'd', 'e', 'r'])
        values = ['a', 'q', 'c', 'd', 'e']
        pd.testing.assert_series_equal(hpat_func(S, values), test_impl(S, values))

    def test_series_isin_set1(self):
        def test_impl(S, values):
            return S.isin(values)
        hpat_func = hpat.jit(test_impl)

        n = 11
        S = pd.Series(np.arange(n))
        values = {1, 2, 5, 7, 8}
        pd.testing.assert_series_equal(hpat_func(S, values), test_impl(S, values))

    def test_series_isin_set2(self):
        def test_impl(S, values):
            return S.isin(values)
        hpat_func = hpat.jit(test_impl)

        n = 11.0
        S = pd.Series(np.arange(n))
        values = {1., 2., 5., 7., 8.}
        pd.testing.assert_series_equal(hpat_func(S, values), test_impl(S, values))

    @unittest.skip('TODO: requires hashable unicode strings in Numba')
    def test_series_isin_set3(self):
        def test_impl(S, values):
            return S.isin(values)
        hpat_func = hpat.jit(test_impl)

        S = pd.Series(['a', 'b', 'c', 'd', 'e'] * 2)
        values = {'b', 'c', 'e'}
        pd.testing.assert_series_equal(hpat_func(S, values), test_impl(S, values))

    def test_series_isna1(self):
        def test_impl(S):
            return S.isna()
        hpat_func = hpat.jit(test_impl)

        # column with NA
        S = pd.Series([np.nan, 2., 3., np.inf])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_isnull1(self):
        def test_impl(S):
            return S.isnull()
        hpat_func = hpat.jit(test_impl)

        # column with NA
        S = pd.Series([np.nan, 2., 3.])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_isnull_full(self):
        def test_impl(series):
            return series.isnull()

        hpat_func = hpat.jit(test_impl)

        for data in test_global_input_data_numeric + [test_global_input_data_unicode_kind4]:
            series = pd.Series(data * 3)
            ref_result = test_impl(series)
            jit_result = hpat_func(series)
            pd.testing.assert_series_equal(ref_result, jit_result)

    def test_series_notna1(self):
        def test_impl(S):
            return S.notna()
        hpat_func = hpat.jit(test_impl)

        # column with NA
        S = pd.Series([np.nan, 2., 3.])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_notna_noidx_float(self):
        def test_impl(S):
            return S.notna()

        hpat_func = hpat.jit(test_impl)
        for input_data in test_global_input_data_float64:
            S = pd.Series(input_data)
            result_ref = test_impl(S)
            result_jit = hpat_func(S)
            pd.testing.assert_series_equal(result_jit, result_ref)

    @unittest.skip("Need fix test_global_input_data_integer64")
    def test_series_notna_noidx_int(self):
        def test_impl(S):
            return S.notna()

        hpat_func = hpat.jit(test_impl)
        for input_data in test_global_input_data_integer64:
            S = pd.Series(input_data)
            result_ref = test_impl(S)
            result_jit = hpat_func(S)
            pd.testing.assert_series_equal(result_jit, result_ref)

    @unittest.skip("Need fix test_global_input_data_integer64")
    def test_series_notna_noidx_num(self):
        def test_impl(S):
            return S.notna()

        hpat_func = hpat.jit(test_impl)
        for input_data in test_global_input_data_numeric:
            S = pd.Series(input_data)
            result_ref = test_impl(S)
            result_jit = hpat_func(S)
            pd.testing.assert_series_equal(result_jit, result_ref)

    def test_series_notna_noidx_str(self):
        def test_impl(S):
            return S.notna()

        hpat_func = hpat.jit(test_impl)
        input_data = test_global_input_data_unicode_kind4
        S = pd.Series(input_data)
        result_ref = test_impl(S)
        result_jit = hpat_func(S)
        pd.testing.assert_series_equal(result_jit, result_ref)

    def test_series_str_notna(self):
        def test_impl(S):
            return S.notna()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series(['aa', None, 'c', 'cccd'])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_str_isna1(self):
        def test_impl(S):
            return S.isna()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series(['aa', None, 'c', 'cccd'])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    @unittest.skip('AssertionError: Series are different')
    def test_series_dt_isna1(self):
        def test_impl(S):
            return S.isna()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([pd.NaT, pd.Timestamp('1970-12-01'), pd.Timestamp('2012-07-25')])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_nlargest1(self):
        def test_impl(S):
            return S.nlargest(4)
        hpat_func = hpat.jit(test_impl)

        m = 100
        np.random.seed(0)
        S = pd.Series(np.random.randint(-30, 30, m))
        np.testing.assert_array_equal(hpat_func(S).values, test_impl(S).values)

    def test_series_nlargest_default1(self):
        def test_impl(S):
            return S.nlargest()
        hpat_func = hpat.jit(test_impl)

        m = 100
        np.random.seed(0)
        S = pd.Series(np.random.randint(-30, 30, m))
        np.testing.assert_array_equal(hpat_func(S).values, test_impl(S).values)

    def test_series_nlargest_nan1(self):
        def test_impl(S):
            return S.nlargest(4)
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([1.0, np.nan, 3.0, 2.0, np.nan, 4.0])
        np.testing.assert_array_equal(hpat_func(S).values, test_impl(S).values)

    def test_series_nlargest_parallel1(self):
        # create `kde.parquet` file
        ParquetGenerator.gen_kde_pq()

        def test_impl():
            df = pq.read_table('kde.parquet').to_pandas()
            S = df.points
            return S.nlargest(4)
        hpat_func = hpat.jit(test_impl)

        np.testing.assert_array_equal(hpat_func().values, test_impl().values)

    @unittest.skip('Unsupported functionality: failed to handle index')
    def test_series_nlargest_index_str(self):
        def test_impl(S):
            return S.nlargest(4)
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([73, 21, 10005, 5, 1], index=['a', 'b', 'c', 'd', 'e'])
        np.testing.assert_array_equal(hpat_func(S).values, test_impl(S).values)

    @unittest.skip('Unsupported functionality: failed to handle index')
    def test_series_nlargest_index_int(self):
        def test_impl(S):
            return S.nlargest(4)

        hpat_func = hpat.jit(test_impl)

        S = pd.Series([73, 21, 10005, 5, 1], index=[2, 3, 4, 5, 6])
        np.testing.assert_array_equal(hpat_func(S).values, test_impl(S).values)

    def test_series_nsmallest1(self):
        def test_impl(S):
            return S.nsmallest(4)
        hpat_func = hpat.jit(test_impl)

        m = 100
        np.random.seed(0)
        S = pd.Series(np.random.randint(-30, 30, m))
        np.testing.assert_array_equal(hpat_func(S).values, test_impl(S).values)

    def test_series_nsmallest_default1(self):
        def test_impl(S):
            return S.nsmallest()
        hpat_func = hpat.jit(test_impl)

        m = 100
        np.random.seed(0)
        S = pd.Series(np.random.randint(-30, 30, m))
        np.testing.assert_array_equal(hpat_func(S).values, test_impl(S).values)

    def test_series_nsmallest_nan1(self):
        def test_impl(S):
            return S.nsmallest(4)
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([1.0, np.nan, 3.0, 2.0, np.nan, 4.0])
        np.testing.assert_array_equal(hpat_func(S).values, test_impl(S).values)

    def test_series_nsmallest_parallel1(self):
        # create `kde.parquet` file
        ParquetGenerator.gen_kde_pq()

        def test_impl():
            df = pq.read_table('kde.parquet').to_pandas()
            S = df.points
            return S.nsmallest(4)
        hpat_func = hpat.jit(test_impl)

        np.testing.assert_array_equal(hpat_func().values, test_impl().values)

    @unittest.skip('Unsupported functionality: failed to handle index')
    def test_series_nsmallest_index_str(self):
        def test_impl(S):
            return S.nsmallest(3)
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([41, 32, 33, 4, 5], index=['a', 'b', 'c', 'd', 'e'])
        np.testing.assert_array_equal(hpat_func(S).values, test_impl(S).values)

    @unittest.skip('Unsupported functionality: failed to handle index')
    def test_series_nsmallest_index_int(self):
        def test_impl(S):
            return S.nsmallest(3)

        hpat_func = hpat.jit(test_impl)

        S = pd.Series([41, 32, 33, 4, 5], index=[1, 2, 3, 4, 5])
        np.testing.assert_array_equal(hpat_func(S).values, test_impl(S).values)

    def test_series_head1(self):
        def test_impl(S):
            return S.head(4)
        hpat_func = hpat.jit(test_impl)

        m = 100
        np.random.seed(0)
        S = pd.Series(np.random.randint(-30, 30, m))
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_head_default1(self):
        '''Verifies default head method for non-distributed pass of Series with no index'''
        def test_impl(S):
            return S.head()
        hpat_func = hpat.jit(test_impl)

        m = 100
        np.random.seed(0)
        S = pd.Series(np.random.randint(-30, 30, m))
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_head_index1(self):
        '''Verifies head method for Series with integer index created inside jitted function'''
        def test_impl():
            S = pd.Series([6, 9, 2, 3, 6, 4, 5], [8, 1, 6, 0, 9, 1, 3])
            return S.head(3)
        hpat_func = hpat.jit(test_impl)

        pd.testing.assert_series_equal(hpat_func(), test_impl())

    def test_series_head_index2(self):
        '''Verifies head method for Series with string index created inside jitted function'''
        def test_impl():
            S = pd.Series([6, 9, 2, 3, 6, 4, 5], ['a', 'ab', 'abc', 'c', 'f', 'hh', ''])
            return S.head(3)
        hpat_func = hpat.jit(test_impl)

        pd.testing.assert_series_equal(hpat_func(), test_impl())

    def test_series_head_index3(self):
        '''Verifies head method for non-distributed pass of Series with integer index'''
        def test_impl(S):
            return S.head(3)
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([6, 9, 2, 3, 6, 4, 5], [8, 1, 6, 0, 9, 1, 3])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    @unittest.skip("Passed if run single")
    def test_series_head_index4(self):
        '''Verifies head method for non-distributed pass of Series with string index'''
        def test_impl(S):
            return S.head(3)
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([6, 9, 2, 4, 6, 4, 5], ['a', 'ab', 'abc', 'c', 'f', 'hh', ''])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_head_parallel1(self):
        '''Verifies head method for distributed Series with string data and no index'''
        def test_impl(S):
            return S.head(7)

        hpat_func = hpat.jit(distributed={'S'})(test_impl)

        # need to test different lenghts, as head's size is fixed and implementation
        # depends on relation of size of the data per processor to output data size
        for n in range(1, 5):
            S = pd.Series(['a', 'ab', 'abc', 'c', 'f', 'hh', ''] * n)
            start, end = get_start_end(len(S))
            pd.testing.assert_series_equal(hpat_func(S[start:end]), test_impl(S))
            self.assertTrue(count_array_OneDs() > 0)

    def test_series_head_index_parallel1(self):
        '''Verifies head method for distributed Series with integer index'''
        def test_impl(S):
            return S.head(3)
        hpat_func = hpat.jit(distributed={'S'})(test_impl)

        S = pd.Series([6, 9, 2, 3, 6, 4, 5], [8, 1, 6, 0, 9, 1, 3])
        start, end = get_start_end(len(S))
        pd.testing.assert_series_equal(hpat_func(S[start:end]), test_impl(S))
        self.assertTrue(count_array_OneDs() > 0)

    @unittest.skip("Passed if run single")
    def test_series_head_index_parallel2(self):
        '''Verifies head method for distributed Series with string index'''
        def test_impl(S):
            return S.head(3)
        hpat_func = hpat.jit(distributed={'S'})(test_impl)

        S = pd.Series([6, 9, 2, 3, 6, 4, 5], ['a', 'ab', 'abc', 'c', 'f', 'hh', ''])
        start, end = get_start_end(len(S))
        pd.testing.assert_series_equal(hpat_func(S[start:end]), test_impl(S))
        self.assertTrue(count_array_OneDs() > 0)

    def test_series_head_noidx_float(self):
        def test_impl(S, n):
            return S.head(n)
        hpat_func = hpat.jit(test_impl)
        for input_data in test_global_input_data_float64:
            S = pd.Series(input_data)
            for n in [-1, 0, 2, 3]:
                result_ref = test_impl(S, n)
                result_jit = hpat_func(S, n)
                pd.testing.assert_series_equal(result_jit, result_ref)

    @unittest.skip("Need fix test_global_input_data_integer64")
    def test_series_head_noidx_int(self):
        def test_impl(S, n):
            return S.head(n)
        hpat_func = hpat.jit(test_impl)
        for input_data in test_global_input_data_integer64:
            S = pd.Series(input_data)
            for n in [-1, 0, 2, 3]:
                result_ref = test_impl(S, n)
                result_jit = hpat_func(S, n)
                pd.testing.assert_series_equal(result_jit, result_ref)

    @unittest.skip("Need fix test_global_input_data_integer64")
    def test_series_head_noidx_num(self):
        def test_impl(S, n):
            return S.head(n)
        hpat_func = hpat.jit(test_impl)
        for input_data in test_global_input_data_numeric:
            S = pd.Series(input_data)
            for n in [-1, 0, 2, 3]:
                result_ref = test_impl(S, n)
                result_jit = hpat_func(S, n)
                pd.testing.assert_series_equal(result_jit, result_ref)

    @unittest.skip("Old implementation not work with n negative and data str")
    def test_series_head_noidx_str(self):
        def test_impl(S, n):
            return S.head(n)
        hpat_func = hpat.jit(test_impl)
        input_data = test_global_input_data_unicode_kind4
        S = pd.Series(input_data)
        for n in [-1, 0, 2, 3]:
            result_ref = test_impl(S, n)
            result_jit = hpat_func(S, n)
            pd.testing.assert_series_equal(result_jit, result_ref)

    @unittest.skip("Broke another three tests")
    def test_series_head_idx(self):
        def test_impl(S):
            return S.head()

        def test_impl_param(S, n):
            return S.head(n)

        hpat_func = hpat.jit(test_impl)

        data_test = [[6, 6, 2, 1, 3, 3, 2, 1, 2],
                     [1.1, 0.3, 2.1, 1, 3, 0.3, 2.1, 1.1, 2.2],
                     [6, 6.1, 2.2, 1, 3, 0, 2.2, 1, 2],
                     ['as', 'b', 'abb', 'sss', 'ytr65', '', 'qw', 'a', 'b'],
                     [6, 6, 2, 1, 3, np.inf, np.nan, np.nan, np.nan],
                     [3., 5.3, np.nan, np.nan, np.inf, np.inf, 4.4, 3.7, 8.9]
                     ]

        for input_data in data_test:
            for index_data in data_test:
                S = pd.Series(input_data, index_data)

                result_ref = test_impl(S)
                result = hpat_func(S)
                pd.testing.assert_series_equal(result, result_ref)

                hpat_func_param1 = hpat.jit(test_impl_param)

                for param1 in [1, 3, 7]:
                    result_param1_ref = test_impl_param(S, param1)
                    result_param1 = hpat_func_param1(S, param1)
                    pd.testing.assert_series_equal(result_param1, result_param1_ref)

    def test_series_median1(self):
        '''Verifies median implementation for float and integer series of random data'''
        def test_impl(S):
            return S.median()
        hpat_func = hpat.jit(test_impl)

        m = 100
        np.random.seed(0)
        S = pd.Series(np.random.randint(-30, 30, m))
        self.assertEqual(hpat_func(S), test_impl(S))

        S = pd.Series(np.random.ranf(m))
        self.assertEqual(hpat_func(S), test_impl(S))

        # odd size
        m = 101
        S = pd.Series(np.random.randint(-30, 30, m))
        self.assertEqual(hpat_func(S), test_impl(S))

        S = pd.Series(np.random.ranf(m))
        self.assertEqual(hpat_func(S), test_impl(S))

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     "BUG: old-style median implementation doesn't filter NaNs")
    def test_series_median_skipna_default1(self):
        '''Verifies median implementation with default skipna=True argument on a series with NA values'''
        def test_impl(S):
            return S.median()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([2., 3., 5., np.nan, 5., 6., 7.])
        self.assertEqual(hpat_func(S), test_impl(S))

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     "Skipna argument is not supported in old-style")
    def test_series_median_skipna_false1(self):
        '''Verifies median implementation with skipna=False on a series with NA values'''
        def test_impl(S):
            return S.median(skipna=False)
        hpat_func = hpat.jit(test_impl)

        # np.inf is not NaN, so verify that a correct number is returned
        S1 = pd.Series([2., 3., 5., np.inf, 5., 6., 7.])
        self.assertEqual(hpat_func(S1), test_impl(S1))

        # TODO: both return values are 'nan', but HPAT's is not np.nan, hence checking with
        # assertIs() doesn't work - check if it's Numba relatated
        S2 = pd.Series([2., 3., 5., np.nan, 5., 6., 7.])
        self.assertEqual(np.isnan(hpat_func(S2)), np.isnan(test_impl(S2)))

    def test_series_median_parallel1(self):
        # create `kde.parquet` file
        ParquetGenerator.gen_kde_pq()

        def test_impl():
            df = pq.read_table('kde.parquet').to_pandas()
            S = df.points
            return S.median()
        hpat_func = hpat.jit(test_impl)

        self.assertEqual(hpat_func(), test_impl())
        self.assertEqual(count_array_REPs(), 0)
        self.assertEqual(count_parfor_REPs(), 0)
        self.assertTrue(count_array_OneDs() > 0)

    def test_series_argsort_parallel(self):
        # create `kde.parquet` file
        ParquetGenerator.gen_kde_pq()

        def test_impl():
            df = pq.read_table('kde.parquet').to_pandas()
            S = df.points
            return S.argsort().values
        hpat_func = hpat.jit(test_impl)

        np.testing.assert_array_equal(hpat_func(), test_impl())

    def test_series_idxmin1(self):
        def test_impl(A):
            return A.idxmin()
        hpat_func = hpat.jit(test_impl)

        n = 11
        np.random.seed(0)
        S = pd.Series(np.random.ranf(n))
        np.testing.assert_array_equal(hpat_func(S), test_impl(S))

    def test_series_idxmin_str(self):
        def test_impl(S):
            return S.idxmin()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([8, 6, 34, np.nan], ['a', 'ab', 'abc', 'c'])
        self.assertEqual(hpat_func(S), test_impl(S))

    @unittest.skip("Skipna is not implemented")
    def test_series_idxmin_str_idx(self):
        def test_impl(S):
            return S.idxmin(skipna=False)

        hpat_func = hpat.jit(test_impl)

        S = pd.Series([8, 6, 34, np.nan], ['a', 'ab', 'abc', 'c'])
        self.assertEqual(hpat_func(S), test_impl(S))

    def test_series_idxmin_no(self):
        def test_impl(S):
            return S.idxmin()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([8, 6, 34, np.nan])
        self.assertEqual(hpat_func(S), test_impl(S))

    def test_series_idxmin_int(self):
        def test_impl(S):
            return S.idxmin()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([1, 2, 3], [4, 45, 14])
        self.assertEqual(hpat_func(S), test_impl(S))

    def test_series_idxmin_noidx(self):
        def test_impl(S):
            return S.idxmin()

        hpat_func = hpat.jit(test_impl)

        data_test = [[6, 6, 2, 1, 3, 3, 2, 1, 2],
                     [1.1, 0.3, 2.1, 1, 3, 0.3, 2.1, 1.1, 2.2],
                     [6, 6.1, 2.2, 1, 3, 0, 2.2, 1, 2],
                     [6, 6, 2, 1, 3, np.inf, np.nan, np.nan, np.nan],
                     [3., 5.3, np.nan, np.nan, np.inf, np.inf, 4.4, 3.7, 8.9]
                     ]

        for input_data in data_test:
            S = pd.Series(input_data)

            result_ref = test_impl(S)
            result = hpat_func(S)
            self.assertEqual(result, result_ref)

    def test_series_idxmin_idx(self):
        def test_impl(S):
            return S.idxmin()

        hpat_func = hpat.jit(test_impl)

        data_test = [[6, 6, 2, 1, 3, 3, 2, 1, 2],
                     [1.1, 0.3, 2.1, 1, 3, 0.3, 2.1, 1.1, 2.2],
                     [6, 6.1, 2.2, 1, 3, 0, 2.2, 1, 2],
                     [6, 6, 2, 1, 3, -np.inf, np.nan, np.inf, np.nan],
                     [3., 5.3, np.nan, np.nan, np.inf, np.inf, 4.4, 3.7, 8.9]
                     ]

        for input_data in data_test:
            for index_data in data_test:
                S = pd.Series(input_data, index_data)
                result_ref = test_impl(S)
                result = hpat_func(S)
                if np.isnan(result) or np.isnan(result_ref):
                    self.assertEqual(np.isnan(result), np.isnan(result_ref))
                else:
                    self.assertEqual(result, result_ref)

    def test_series_idxmax1(self):
        def test_impl(A):
            return A.idxmax()
        hpat_func = hpat.jit(test_impl)

        n = 11
        np.random.seed(0)
        S = pd.Series(np.random.ranf(n))
        np.testing.assert_array_equal(hpat_func(S), test_impl(S))

    @unittest.skip("Skipna is not implemented")
    def test_series_idxmax_str_idx(self):
        def test_impl(S):
            return S.idxmax(skipna=False)

        hpat_func = hpat.jit(test_impl)

        S = pd.Series([8, 6, 34, np.nan], ['a', 'ab', 'abc', 'c'])
        self.assertEqual(hpat_func(S), test_impl(S))

    def test_series_idxmax_noidx(self):
        def test_impl(S):
            return S.idxmax()

        hpat_func = hpat.jit(test_impl)

        data_test = [[6, 6, 2, 1, 3, 3, 2, 1, 2],
                     [1.1, 0.3, 2.1, 1, 3, 0.3, 2.1, 1.1, 2.2],
                     [6, 6.1, 2.2, 1, 3, 0, 2.2, 1, 2],
                     [6, 6, 2, 1, 3, np.inf, np.nan, np.inf, np.nan],
                     [3., 5.3, np.nan, np.nan, np.inf, np.inf, 4.4, 3.7, 8.9]
                     ]

        for input_data in data_test:
            S = pd.Series(input_data)

            result_ref = test_impl(S)
            result = hpat_func(S)
            self.assertEqual(result, result_ref)

    def test_series_idxmax_idx(self):
        def test_impl(S):
            return S.idxmax()

        hpat_func = hpat.jit(test_impl)

        data_test = [[6, 6, 2, 1, 3, 3, 2, 1, 2],
                     [1.1, 0.3, 2.1, 1, 3, 0.3, 2.1, 1.1, 2.2],
                     [6, 6.1, 2.2, 1, 3, 0, 2.2, 1, 2],
                     [6, 6, 2, 1, 3, np.nan, np.nan, np.nan, np.nan],
                     [3., 5.3, np.nan, np.nan, np.inf, np.inf, 4.4, 3.7, 8.9]
                     ]

        for input_data in data_test:
            for index_data in data_test:
                S = pd.Series(input_data, index_data)
                result_ref = test_impl(S)
                result = hpat_func(S)
                if np.isnan(result) or np.isnan(result_ref):
                    self.assertEqual(np.isnan(result), np.isnan(result_ref))
                else:
                    self.assertEqual(result, result_ref)

    def test_series_sort_values1(self):
        def test_impl(A):
            return A.sort_values()
        hpat_func = hpat.jit(test_impl)

        n = 11
        np.random.seed(0)
        S = pd.Series(np.random.ranf(n))
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_sort_values_index1(self):
        def test_impl(A, B):
            S = pd.Series(A, B)
            return S.sort_values()
        hpat_func = hpat.jit(test_impl)

        n = 11
        np.random.seed(0)
        # TODO: support passing Series with Index
        # S = pd.Series(np.random.ranf(n), np.random.randint(0, 100, n))
        A = np.random.ranf(n)
        B = np.random.ranf(n)
        pd.testing.assert_series_equal(hpat_func(A, B), test_impl(A, B))

    def test_series_sort_values_parallel1(self):
        # create `kde.parquet` file
        ParquetGenerator.gen_kde_pq()

        def test_impl():
            df = pq.read_table('kde.parquet').to_pandas()
            S = df.points
            return S.sort_values()
        hpat_func = hpat.jit(test_impl)

        np.testing.assert_array_equal(hpat_func(), test_impl())

    def test_series_shift(self):
        def pyfunc():
            series = pd.Series([1.0, np.nan, -1.0, 0.0, 5e-324])
            return series.shift()

        cfunc = hpat.jit(pyfunc)
        pd.testing.assert_series_equal(cfunc(), pyfunc())

    def test_series_shift_unboxing(self):
        def pyfunc(series):
            return series.shift()

        cfunc = hpat.jit(pyfunc)
        for data in test_global_input_data_float64:
            series = pd.Series(data)
            pd.testing.assert_series_equal(cfunc(series), pyfunc(series))

    def test_series_shift_full(self):
        def pyfunc(series, periods, freq, axis, fill_value):
            return series.shift(periods=periods, freq=freq, axis=axis, fill_value=fill_value)

        cfunc = hpat.jit(pyfunc)
        freq = None
        axis = 0
        for data in test_global_input_data_float64:
            series = pd.Series(data)
            for periods in [-2, 0, 3]:
                for fill_value in [9.1, np.nan, -3.3, None]:
                    jit_result = cfunc(series, periods, freq, axis, fill_value)
                    ref_result = pyfunc(series, periods, freq, axis, fill_value)
                    pd.testing.assert_series_equal(jit_result, ref_result)

    def test_series_shift_str(self):
        def pyfunc(series):
            return series.shift()

        cfunc = hpat.jit(pyfunc)
        series = pd.Series(test_global_input_data_unicode_kind4)
        with self.assertRaises(TypingError) as raises:
            cfunc(series)
        msg = 'Method shift(). The object must be a number. Given self.data.dtype: {}'
        self.assertIn(msg.format(types.unicode_type), str(raises.exception))

    def test_series_shift_fill_str(self):
        def pyfunc(series, fill_value):
            return series.shift(fill_value=fill_value)

        cfunc = hpat.jit(pyfunc)
        series = pd.Series(test_global_input_data_float64[0])
        with self.assertRaises(TypingError) as raises:
            cfunc(series, fill_value='unicode')
        msg = 'Method shift(). The object must be a number. Given fill_value: {}'
        self.assertIn(msg.format(types.unicode_type), str(raises.exception))

    def test_series_shift_unsupported_params(self):
        def pyfunc(series, freq, axis):
            return series.shift(freq=freq, axis=axis)

        cfunc = hpat.jit(pyfunc)
        series = pd.Series(test_global_input_data_float64[0])
        with self.assertRaises(TypingError) as raises:
            cfunc(series, freq='12H', axis=0)
        msg = 'Method shift(). Unsupported parameters. Given freq: {}'
        self.assertIn(msg.format(types.unicode_type), str(raises.exception))

        with self.assertRaises(TypingError) as raises:
            cfunc(series, freq=None, axis=1)
        msg = 'Method shift(). Unsupported parameters. Given axis != 0'
        self.assertIn(msg, str(raises.exception))

    @unittest.skip('Unsupported functionality: failed to handle index')
    def test_series_shift_index_str(self):
        def test_impl(S):
            return S.shift()
        hpat_func = hpat.jit(test_impl)

        S = pd.Series([np.nan, 2., 3., 5., np.nan, 6., 7.], index=['a', 'b', 'c', 'd', 'e', 'f', 'g'])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    @unittest.skip('Unsupported functionality: failed to handle index')
    def test_series_shift_index_int(self):
        def test_impl(S):
            return S.shift()

        hpat_func = hpat.jit(test_impl)

        S = pd.Series([np.nan, 2., 3., 5., np.nan, 6., 7.], index=[1, 2, 3, 4, 5, 6, 7])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_series_index1(self):
        def test_impl():
            A = pd.Series([1, 2, 3], index=['A', 'C', 'B'])
            return A.index

        hpat_func = hpat.jit(test_impl)
        np.testing.assert_array_equal(hpat_func(), test_impl())

    def test_series_index2(self):
        def test_impl():
            A = pd.Series([1, 2, 3], index=[0, 1, 2])
            return A.index

        hpat_func = hpat.jit(test_impl)
        np.testing.assert_array_equal(hpat_func(), test_impl())

    def test_series_index3(self):
        def test_impl():
            A = pd.Series([1, 2, 3])
            return A.index

        hpat_func = hpat.jit(test_impl)
        np.testing.assert_array_equal(hpat_func(), test_impl())

    def test_series_take_index_default(self):
        def pyfunc():
            series = pd.Series([1.0, 13.0, 9.0, -1.0, 7.0])
            indices = [1, 3]
            return series.take(indices)

        cfunc = hpat.jit(pyfunc)
        ref_result = pyfunc()
        result = cfunc()
        pd.testing.assert_series_equal(ref_result, result)

    def test_series_take_index_default_unboxing(self):
        def pyfunc(series, indices):
            return series.take(indices)

        cfunc = hpat.jit(pyfunc)
        series = pd.Series([1.0, 13.0, 9.0, -1.0, 7.0])
        indices = [1, 3]
        ref_result = pyfunc(series, indices)
        result = cfunc(series, indices)
        pd.testing.assert_series_equal(ref_result, result)

    def test_series_take_index_int(self):
        def pyfunc():
            series = pd.Series([1.0, 13.0, 9.0, -1.0, 7.0], index=[3, 0, 4, 2, 1])
            indices = [1, 3]
            return series.take(indices)

        cfunc = hpat.jit(pyfunc)
        ref_result = pyfunc()
        result = cfunc()
        pd.testing.assert_series_equal(ref_result, result)

    def test_series_take_index_int_unboxing(self):
        def pyfunc(series, indices):
            return series.take(indices)

        cfunc = hpat.jit(pyfunc)
        series = pd.Series([1.0, 13.0, 9.0, -1.0, 7.0], index=[3, 0, 4, 2, 1])
        indices = [1, 3]
        ref_result = pyfunc(series, indices)
        result = cfunc(series, indices)
        pd.testing.assert_series_equal(ref_result, result)

    def test_series_take_index_str(self):
        def pyfunc():
            series = pd.Series([1.0, 13.0, 9.0, -1.0, 7.0], index=['test', 'series', 'take', 'str', 'index'])
            indices = [1, 3]
            return series.take(indices)

        cfunc = hpat.jit(pyfunc)
        ref_result = pyfunc()
        result = cfunc()
        pd.testing.assert_series_equal(ref_result, result)

    def test_series_take_index_str_unboxing(self):
        def pyfunc(series, indices):
            return series.take(indices)

        cfunc = hpat.jit(pyfunc)
        series = pd.Series([1.0, 13.0, 9.0, -1.0, 7.0], index=['test', 'series', 'take', 'str', 'index'])
        indices = [1, 3]
        ref_result = pyfunc(series, indices)
        result = cfunc(series, indices)
        pd.testing.assert_series_equal(ref_result, result)

    def test_series_iterator_int(self):
        def test_impl(A):
            return [i for i in A]

        A = pd.Series([3, 2, 1, 5, 4])
        hpat_func = hpat.jit(test_impl)
        np.testing.assert_array_equal(hpat_func(A), test_impl(A))

    def test_series_iterator_float(self):
        def test_impl(A):
            return [i for i in A]

        A = pd.Series([0.3, 0.2222, 0.1756, 0.005, 0.4])
        hpat_func = hpat.jit(test_impl)
        np.testing.assert_array_equal(hpat_func(A), test_impl(A))

    def test_series_iterator_boolean(self):
        def test_impl(A):
            return [i for i in A]

        A = pd.Series([True, False])
        hpat_func = hpat.jit(test_impl)
        np.testing.assert_array_equal(hpat_func(A), test_impl(A))

    def test_series_iterator_string(self):
        def test_impl(A):
            return [i for i in A]

        A = pd.Series(['a', 'ab', 'abc', '', 'dddd'])
        hpat_func = hpat.jit(test_impl)
        np.testing.assert_array_equal(hpat_func(A), test_impl(A))

    def test_series_iterator_one_value(self):
        def test_impl(A):
            return [i for i in A]

        A = pd.Series([5])
        hpat_func = hpat.jit(test_impl)
        np.testing.assert_array_equal(hpat_func(A), test_impl(A))

    @unittest.skip("Fails when NUMA_PES>=2 due to unimplemented sync of such construction after distribution")
    def test_series_iterator_no_param(self):
        def test_impl():
            A = pd.Series([3, 2, 1, 5, 4])
            return [i for i in A]

        hpat_func = hpat.jit(test_impl)
        np.testing.assert_array_equal(hpat_func(), test_impl())

    def test_series_iterator_empty(self):
        def test_impl(A):
            return [i for i in A]

        A = pd.Series([np.int64(x) for x in range(0)])
        hpat_func = hpat.jit(test_impl)
        np.testing.assert_array_equal(hpat_func(A), test_impl(A))

    def test_series_default_index(self):
        def test_impl():
            A = pd.Series([3, 2, 1, 5, 4])
            return A.index

        hpat_func = hpat.jit(test_impl)
        np.testing.assert_array_equal(hpat_func(), test_impl())

    @unittest.skip("Implement drop_duplicates for Series")
    def test_series_drop_duplicates(self):
        def test_impl():
            A = pd.Series(['lama', 'cow', 'lama', 'beetle', 'lama', 'hippo'])
            return A.drop_duplicates()

        hpat_func = hpat.jit(test_impl)
        pd.testing.assert_series_equal(hpat_func(), test_impl())

    def test_series_quantile(self):
        def test_impl():
            A = pd.Series([1, 2.5, .5, 3, 5])
            return A.quantile()

        hpat_func = hpat.jit(test_impl)
        np.testing.assert_equal(hpat_func(), test_impl())

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default, "Series.quantile() parameter as a list unsupported")
    def test_series_quantile_q_vector(self):
        def test_series_quantile_q_vector_impl(S, param1):
            return S.quantile(param1)

        S = pd.Series(np.random.ranf(100))
        hpat_func = hpat.jit(test_series_quantile_q_vector_impl)

        param1 = [0.0, 0.25, 0.5, 0.75, 1.0]
        result_ref = test_series_quantile_q_vector_impl(S, param1)
        result = hpat_func(S, param1)
        np.testing.assert_equal(result, result_ref)

    @unittest.skip("Implement unique without sorting like in pandas")
    def test_unique(self):
        def test_impl(S):
            return S.unique()

        hpat_func = hpat.jit(test_impl)
        S = pd.Series([2, 1, 3, 3])
        pd.testing.assert_series_equal(hpat_func(S), test_impl(S))

    def test_unique_sorted(self):
        def test_impl(S):
            return S.unique()

        hpat_func = hpat.jit(test_impl)
        n = 11
        S = pd.Series(np.arange(n))
        S[2] = 0
        np.testing.assert_array_equal(hpat_func(S), test_impl(S))

    def test_unique_str(self):
        def test_impl():
            data = pd.Series(['aa', 'aa', 'b', 'b', 'cccc', 'dd', 'ddd', 'dd'])
            return data.unique()

        hpat_func = hpat.jit(test_impl)

        # since the orider of the elements are diffrent - check count of elements only
        ref_result = test_impl().size
        result = hpat_func().size
        np.testing.assert_array_equal(ref_result, result)

    def test_series_groupby_count(self):
        def test_impl():
            A = pd.Series([13, 11, 21, 13, 13, 51, 42, 21])
            grouped = A.groupby(A, sort=False)
            return grouped.count()

        hpat_func = hpat.jit(test_impl)

        ref_result = test_impl()
        result = hpat_func()
        pd.testing.assert_series_equal(result, ref_result)

    @unittest.skip("getiter for this type is not implemented yet")
    def test_series_groupby_iterator_int(self):
        def test_impl():
            A = pd.Series([13, 11, 21, 13, 13, 51, 42, 21])
            grouped = A.groupby(A)
            return [i for i in grouped]

        hpat_func = hpat.jit(test_impl)

        ref_result = test_impl()
        result = hpat_func()
        np.testing.assert_array_equal(result, ref_result)

    def test_series_std(self):
        def pyfunc():
            series = pd.Series([1.0, np.nan, -1.0, 0.0, 5e-324])
            return series.std()

        cfunc = hpat.jit(pyfunc)
        ref_result = pyfunc()
        result = cfunc()
        np.testing.assert_equal(ref_result, result)

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     'Series.std() parameters "skipna" and "ddof" unsupported')
    def test_series_std_unboxing(self):
        def pyfunc(series, skipna, ddof):
            return series.std(skipna=skipna, ddof=ddof)

        cfunc = hpat.jit(pyfunc)
        for data in test_global_input_data_numeric + [[]]:
            series = pd.Series(data)
            for ddof in [0, 1]:
                for skipna in [True, False]:
                    ref_result = pyfunc(series, skipna=skipna, ddof=ddof)
                    result = cfunc(series, skipna=skipna, ddof=ddof)
                    np.testing.assert_equal(ref_result, result)

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     'Series.std() strings as input data unsupported')
    def test_series_std_str(self):
        def pyfunc(series):
            return series.std()

        cfunc = hpat.jit(pyfunc)
        series = pd.Series(test_global_input_data_unicode_kind4)
        with self.assertRaises(TypingError) as raises:
            cfunc(series)
        msg = 'Method std(). The object must be a number. Given self.data.dtype: {}'
        self.assertIn(msg.format(types.unicode_type), str(raises.exception))

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     'Series.std() parameters "axis", "level", "numeric_only" unsupported')
    def test_series_std_unsupported_params(self):
        def pyfunc(series, axis, level, numeric_only):
            return series.std(axis=axis, level=level, numeric_only=numeric_only)

        cfunc = hpat.jit(pyfunc)
        series = pd.Series(test_global_input_data_float64[0])
        msg = 'Method std(). Unsupported parameters. Given {}: {}'
        with self.assertRaises(TypingError) as raises:
            cfunc(series, axis=1, level=None, numeric_only=None)
        self.assertIn(msg.format('axis', 'int'), str(raises.exception))

        with self.assertRaises(TypingError) as raises:
            cfunc(series, axis=None, level=1, numeric_only=None)
        self.assertIn(msg.format('level', 'int'), str(raises.exception))

        with self.assertRaises(TypingError) as raises:
            cfunc(series, axis=None, level=None, numeric_only=True)
        self.assertIn(msg.format('numeric_only', 'bool'), str(raises.exception))

    def test_series_nunique(self):
        def test_series_nunique_impl(S):
            return S.nunique()

        def test_series_nunique_param1_impl(S, dropna):
            return S.nunique(dropna)

        hpat_func = hpat.jit(test_series_nunique_impl)

        the_same_string = "the same string"
        test_input_data = []
        data_simple = [[6, 6, 2, 1, 3, 3, 2, 1, 2],
                       [1.1, 0.3, 2.1, 1, 3, 0.3, 2.1, 1.1, 2.2],
                       [6, 6.1, 2.2, 1, 3, 3, 2.2, 1, 2],
                       ['aa', 'aa', 'b', 'b', 'cccc', 'dd', 'ddd', 'dd'],
                       ['aa', 'copy aa', the_same_string, 'b', 'b', 'cccc', the_same_string, 'dd', 'ddd', 'dd', 'copy aa', 'copy aa'],
                       []
                       ]

        data_extra = [[6, 6, np.nan, 2, np.nan, 1, 3, 3, np.inf, 2, 1, 2, np.inf],
                      [1.1, 0.3, np.nan, 1.0, np.inf, 0.3, 2.1, np.nan, 2.2, np.inf],
                      [1.1, 0.3, np.nan, 1, np.inf, 0, 1.1, np.nan, 2.2, np.inf, 2, 2],
                      # unsupported ['aa', np.nan, 'b', 'b', 'cccc', np.nan, 'ddd', 'dd'],
                      # unsupported [np.nan, 'copy aa', the_same_string, 'b', 'b', 'cccc', the_same_string, 'dd', 'ddd', 'dd', 'copy aa', 'copy aa'],
                      [np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.inf],
                      ]

        if hpat.config.config_pipeline_hpat_default:
            """
            HPAT pipeline Series.nunique() does not support numpy.nan
            """

            test_input_data = data_simple
        else:
            test_input_data = data_simple + data_extra

        for input_data in test_input_data:
            S = pd.Series(input_data)

            result_ref = test_series_nunique_impl(S)
            result = hpat_func(S)
            self.assertEqual(result, result_ref)

            if not hpat.config.config_pipeline_hpat_default:
                """
                HPAT pipeline does not support parameter to Series.nunique(dropna=True)
                """

                hpat_func_param1 = hpat.jit(test_series_nunique_param1_impl)

                for param1 in [True, False]:
                    result_param1_ref = test_series_nunique_param1_impl(S, param1)
                    result_param1 = hpat_func_param1(S, param1)
                    self.assertEqual(result_param1, result_param1_ref)

    def test_series_var(self):
        def pyfunc():
            series = pd.Series([1.0, np.nan, -1.0, 0.0, 5e-324])
            return series.var()

        cfunc = hpat.jit(pyfunc)
        np.testing.assert_equal(pyfunc(), cfunc())

    def test_series_var_unboxing(self):
        def pyfunc(series):
            return series.var()

        cfunc = hpat.jit(pyfunc)
        for data in test_global_input_data_numeric + [[]]:
            series = pd.Series(data)
            np.testing.assert_equal(pyfunc(series), cfunc(series))

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     'Series.var() parameters "ddof" and "skipna" unsupported')
    def test_series_var_full(self):
        def pyfunc(series, skipna, ddof):
            return series.var(skipna=skipna, ddof=ddof)

        cfunc = hpat.jit(pyfunc)
        for data in test_global_input_data_numeric + [[]]:
            series = pd.Series(data)
            for ddof in [0, 1]:
                for skipna in [True, False]:
                    ref_result = pyfunc(series, skipna=skipna, ddof=ddof)
                    result = cfunc(series, skipna=skipna, ddof=ddof)
                    np.testing.assert_equal(ref_result, result)

    def test_series_var_str(self):
        def pyfunc(series):
            return series.var()

        cfunc = hpat.jit(pyfunc)
        series = pd.Series(test_global_input_data_unicode_kind4)
        with self.assertRaises(TypingError) as raises:
            cfunc(series)
        msg = 'Method var(). The object must be a number. Given self.data.dtype: {}'
        self.assertIn(msg.format(types.unicode_type), str(raises.exception))

    def test_series_var_unsupported_params(self):
        def pyfunc(series, axis, level, numeric_only):
            return series.var(axis=axis, level=level, numeric_only=numeric_only)

        cfunc = hpat.jit(pyfunc)
        series = pd.Series(test_global_input_data_float64[0])
        msg = 'Method var(). Unsupported parameters. Given {}: {}'
        with self.assertRaises(TypingError) as raises:
            cfunc(series, axis=1, level=None, numeric_only=None)
        self.assertIn(msg.format('axis', 'int'), str(raises.exception))

        with self.assertRaises(TypingError) as raises:
            cfunc(series, axis=None, level=1, numeric_only=None)
        self.assertIn(msg.format('level', 'int'), str(raises.exception))

        with self.assertRaises(TypingError) as raises:
            cfunc(series, axis=None, level=None, numeric_only=True)
        self.assertIn(msg.format('numeric_only', 'bool'), str(raises.exception))

    def test_series_count(self):
        def test_series_count_impl(S):
            return S.count()

        hpat_func = hpat.jit(test_series_count_impl)

        the_same_string = "the same string"
        test_input_data = [[6, 6, 2, 1, 3, 3, 2, 1, 2],
                           [1.1, 0.3, 2.1, 1, 3, 0.3, 2.1, 1.1, 2.2],
                           [6, 6.1, 2.2, 1, 3, 3, 2.2, 1, 2],
                           ['aa', 'aa', 'b', 'b', 'cccc', 'dd', 'ddd', 'dd'],
                           ['aa', 'copy aa', the_same_string, 'b', 'b', 'cccc', the_same_string, 'dd', 'ddd', 'dd',
                            'copy aa', 'copy aa'],
                           [],
                           [6, 6, np.nan, 2, np.nan, 1, 3, 3, np.inf, 2, 1, 2, np.inf],
                           [1.1, 0.3, np.nan, 1.0, np.inf, 0.3, 2.1, np.nan, 2.2, np.inf],
                           [1.1, 0.3, np.nan, 1, np.inf, 0, 1.1, np.nan, 2.2, np.inf, 2, 2],
                           [np.nan, np.nan, np.nan],
                           [np.nan, np.nan, np.inf]
                           ]

        for input_data in test_input_data:
            S = pd.Series(input_data)

            result_ref = test_series_count_impl(S)
            result = hpat_func(S)
            self.assertEqual(result, result_ref)

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     'Series.cumsum() np.nan as input data unsupported')
    def test_series_cumsum(self):
        def test_impl():
            series = pd.Series([1.0, np.nan, -1.0, 0.0, 5e-324])
            return series.cumsum()

        pyfunc = test_impl
        cfunc = hpat.jit(pyfunc)
        pd.testing.assert_series_equal(pyfunc(), cfunc())

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     'Series.cumsum() np.nan as input data unsupported')
    def test_series_cumsum_unboxing(self):
        def test_impl(s):
            return s.cumsum()

        pyfunc = test_impl
        cfunc = hpat.jit(pyfunc)

        for data in test_global_input_data_numeric + [[]]:
            series = pd.Series(data)
            pd.testing.assert_series_equal(pyfunc(series), cfunc(series))

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     'Series.cumsum() parameters "axis", "skipna" unsupported')
    def test_series_cumsum_full(self):
        def test_impl(s, axis, skipna):
            return s.cumsum(axis=axis, skipna=skipna)

        pyfunc = test_impl
        cfunc = hpat.jit(pyfunc)

        axis = None
        for data in test_global_input_data_numeric + [[]]:
            series = pd.Series(data)
            for skipna in [True, False]:
                ref_result = pyfunc(series, axis=axis, skipna=skipna)
                jit_result = cfunc(series, axis=axis, skipna=skipna)
                pd.testing.assert_series_equal(ref_result, jit_result)

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     'Series.cumsum() strings as input data unsupported')
    def test_series_cumsum_str(self):
        def test_impl(s):
            return s.cumsum()

        cfunc = hpat.jit(test_impl)
        series = pd.Series(test_global_input_data_unicode_kind4)
        with self.assertRaises(TypingError) as raises:
            cfunc(series)
        msg = 'Method cumsum(). The object must be a number. Given self.data.dtype: {}'
        self.assertIn(msg.format(types.unicode_type), str(raises.exception))

    @unittest.skipIf(hpat.config.config_pipeline_hpat_default,
                     'Series.cumsum() parameter "axis" unsupported')
    def test_series_cumsum_unsupported_axis(self):
        def test_impl(s, axis):
            return s.cumsum(axis=axis)

        cfunc = hpat.jit(test_impl)
        series = pd.Series(test_global_input_data_float64[0])
        for axis in [0, 1]:
            with self.assertRaises(TypingError) as raises:
                cfunc(series, axis=axis)
            msg = 'Method cumsum(). Unsupported parameters. Given axis: int'
            self.assertIn(msg, str(raises.exception))


if __name__ == "__main__":
    unittest.main()
