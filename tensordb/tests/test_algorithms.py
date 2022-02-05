import pandas as pd
import xarray as xr
import os
import numpy as np
import pytest

from typing import List, Dict
from loguru import logger

from tensordb.algorithms import Algorithms


# TODO: Add more tests for the dataset cases


class TestAlgorithms:

    def test_ffill(self):
        arr = xr.DataArray(
            [
                [1, np.nan, np.nan, np.nan, np.nan, np.nan],
                [1, np.nan, np.nan, 2, np.nan, np.nan],
                [np.nan, 5, np.nan, 2, np.nan, np.nan],
            ],
            dims=['a', 'b'],
            coords={'a': list(range(3)), 'b': list(range(6))}
        ).chunk(
            (1, 2)
        )
        assert Algorithms.ffill(arr, limit=2, dim='b').equals(arr.compute().ffill('b', limit=2))
        assert Algorithms.ffill(arr, limit=2, dim='b', until_last_valid=True).equals(
            xr.DataArray(
                [
                    [1, np.nan, np.nan, np.nan, np.nan, np.nan],
                    [1, 1, 1, 2, np.nan, np.nan],
                    [np.nan, 5, 5, 2, np.nan, np.nan],
                ],
                dims=['a', 'b'],
                coords={'a': list(range(3)), 'b': list(range(6))}
            )
        )

    def test_rolling_along_axis(self):
        arr = xr.DataArray(
            [
                [1,         np.nan, 3],
                [np.nan,    4,      6],
                [np.nan,    5,      np.nan],
                [3,         np.nan, 7],
                [7,         6,      np.nan]
            ],
            dims=['a', 'b'],
            coords={'a': list(range(5)), 'b': list(range(3))}
        ).chunk((3, 1))
        df = pd.DataFrame(arr.values.T, arr.b.values, arr.a.values).stack(dropna=False)
        for window in range(1, 4):
            for min_periods in [None] + list(range(1, window)):
                for drop_nan in [True, False]:
                    for fill_method in [None, 'ffill']:
                        rolling_arr = Algorithms.rolling_along_axis(
                            arr,
                            window=window,
                            dim='a',
                            operator='mean',
                            min_periods=min_periods,
                            drop_nan=drop_nan,
                            fill_method=fill_method
                        )

                        expected = df
                        if drop_nan:
                            expected = expected.dropna()
                        expected = expected.groupby(level=0).rolling(window=window, min_periods=min_periods).mean()
                        expected = expected.droplevel(0).unstack(0)

                        if fill_method == 'ffill' and drop_nan:
                            expected.ffill(inplace=True)

                        expected = xr.DataArray(expected.values, coords=arr.coords, dims=arr.dims)
                        assert expected.equals(rolling_arr)

    def test_replace(self):
        arr = xr.DataArray(
            [
                [1, 2, 3],
                [4, 4, 1],
                [5, 2, 3],
                [np.nan, 3, 0],
                [8, 7, 9]
            ],
            dims=['a', 'b'],
            coords={'a': list(range(5)), 'b': list(range(3))}
        ).chunk((3, 1))

        df = pd.DataFrame(arr.values, index=arr.a.values, columns=arr.b.values)

        to_replace = {
            1: 11,
            2: 12,
            3: 13,
            4: 14,
            5: 15,
            7: 16
        }

        for method in ('vectorized', 'unique'):
            for default_value in [None, np.nan]:
                new_data = Algorithms.replace(
                    new_data=arr,
                    method=method,
                    to_replace=to_replace,
                    dtype=float,
                    default_value=default_value
                )
                replaced_df = df.replace(to_replace)
                if default_value is not None:
                    replaced_df.values[~np.isin(df.values, list(to_replace.keys()))] = default_value

                assert xr.DataArray(
                    replaced_df.values,
                    coords={'a': replaced_df.index, 'b': replaced_df.columns},
                    dims=['a', 'b']
                ).equals(
                    new_data
                )

    def test_vindex(self):
        arr = xr.DataArray(
            [
                [[1, 3], [4, 1], [5, 2]],
                [[4, 2], [5, 1], [3, 4]],
                [[5, 1], [2, -1], [3, -5]],
                [[np.nan, 1], [3, 3], [0, -2]],
                [[8, 3], [7, 5], [9, 11]]
            ],
            dims=['a', 'b', 'c'],
            coords={'a': list(range(5)), 'b': list(range(3)), 'c': list(range(2))}
        ).chunk((3, 2, 1))

        for i_coord in [None, [0, 3, 1, 4], [3, 4, 2, 1], [1, 1, 1]]:
            for j_coord in [None, [1, 0, 2], [2, 1, 0], [0, 0 ,0], [1, 0]]:
                for k_coord in [None, [0, 1], [1, 0], [0], [1]]:
                    coords = {'a': i_coord, 'b': j_coord, 'c': k_coord}
                    coords = {k: v for k, v in coords.items() if v is not None}
                    if len(coords) == 0:
                        continue
                    expected = arr.reindex(coords)
                    result = Algorithms.vindex(arr, coords)
                    assert expected.equals(result)

    def test_merge_duplicates_coord(self):
        arr = xr.DataArray(
            [
                [1, 2, 3, 4, 3],
                [4, 4, 1, 3, 5],
                [5, 2, 3, 2, 1],
                [np.nan, 3, 0, 5, 4],
                [8, 7, 9, 6, 7]
            ],
            dims=['a', 'b'],
            coords={'a': list(range(5)), 'b': [0, 1, 1, 0, -1]}
        ).chunk((3, 2))

        g = arr.groupby('b').max('b')
        assert g.equals(Algorithms.merge_duplicates_coord(arr, 'b','max'))


if __name__ == "__main__":
    test = TestAlgorithms()
    # test.test_ffill()
    test.test_replace()
    # test.test_append_data(remote=False)
    # test.test_update_data()
    # test.test_backup()
