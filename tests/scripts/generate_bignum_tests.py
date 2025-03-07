#!/usr/bin/env python3
"""Generate test data for bignum functions.

With no arguments, generate all test data. With non-option arguments,
generate only the specified files.

Class structure:

Child classes of test_data_generation.BaseTarget (file targets) represent an output
file. These indicate where test cases will be written to, for all subclasses of
this target. Multiple file targets should not reuse a `target_basename`.

Each subclass derived from a file target can either be:
  - A concrete class, representing a test function, which generates test cases.
  - An abstract class containing shared methods and attributes, not associated
        with a test function. An example is BignumOperation, which provides
        common features used for bignum binary operations.

Both concrete and abstract subclasses can be derived from, to implement
additional test cases (see BignumCmp and BignumCmpAbs for examples of deriving
from abstract and concrete classes).


Adding test case generation for a function:

A subclass representing the test function should be added, deriving from a
file target such as BignumTarget. This test class must set/implement the
following:
  - test_function: the function name from the associated .function file.
  - test_name: a descriptive name or brief summary to refer to the test
        function.
  - arguments(): a method to generate the list of arguments required for the
        test_function.
  - generate_function_tests(): a method to generate TestCases for the function.
        This should create instances of the class with required input data, and
        call `.create_test_case()` to yield the TestCase.

Additional details and other attributes/methods are given in the documentation
of BaseTarget in test_data_generation.py.
"""

# Copyright The Mbed TLS Contributors
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import itertools
import sys
import typing

from abc import ABCMeta, abstractmethod
from typing import Iterator, List, Tuple, TypeVar

import scripts_path # pylint: disable=unused-import
from mbedtls_dev import test_case
from mbedtls_dev import test_data_generation

T = TypeVar('T') #pylint: disable=invalid-name

def hex_to_int(val: str) -> int:
    return int(val, 16) if val else 0

def quote_str(val) -> str:
    return "\"{}\"".format(val)

def combination_pairs(values: List[T]) -> List[Tuple[T, T]]:
    """Return all pair combinations from input values."""
    # The return value is cast, as older versions of mypy are unable to derive
    # the specific type returned by itertools.combinations_with_replacement.
    return typing.cast(
        List[Tuple[T, T]],
        list(itertools.combinations_with_replacement(values, 2))
    )


class BignumTarget(test_data_generation.BaseTarget, metaclass=ABCMeta):
    #pylint: disable=abstract-method
    """Target for bignum (mpi) test case generation."""
    target_basename = 'test_suite_mpi.generated'


class BignumOperation(BignumTarget, metaclass=ABCMeta):
    """Common features for bignum binary operations.

    This adds functionality common in binary operation tests. This includes
    generation of case descriptions, using descriptions of values and symbols
    to represent the operation or result.

    Attributes:
        symbol: Symbol used for the operation in case description.
        input_values: List of values to use as test case inputs. These are
            combined to produce pairs of values.
        input_cases: List of tuples containing pairs of test case inputs. This
            can be used to implement specific pairs of inputs.
    """
    symbol = ""
    input_values = [
        "", "0", "7b", "-7b",
        "0000000000000000123", "-0000000000000000123",
        "1230000000000000000", "-1230000000000000000"
    ] # type: List[str]
    input_cases = [] # type: List[Tuple[str, str]]

    def __init__(self, val_a: str, val_b: str) -> None:
        self.arg_a = val_a
        self.arg_b = val_b
        self.int_a = hex_to_int(val_a)
        self.int_b = hex_to_int(val_b)

    def arguments(self) -> List[str]:
        return [quote_str(self.arg_a), quote_str(self.arg_b), self.result()]

    def description(self) -> str:
        """Generate a description for the test case.

        If not set, case_description uses the form A `symbol` B, where symbol
        is used to represent the operation. Descriptions of each value are
        generated to provide some context to the test case.
        """
        if not self.case_description:
            self.case_description = "{} {} {}".format(
                self.value_description(self.arg_a),
                self.symbol,
                self.value_description(self.arg_b)
            )
        return super().description()

    @abstractmethod
    def result(self) -> str:
        """Get the result of the operation.

        This could be calculated during initialization and stored as `_result`
        and then returned, or calculated when the method is called.
        """
        raise NotImplementedError

    @staticmethod
    def value_description(val) -> str:
        """Generate a description of the argument val.

        This produces a simple description of the value, which is used in test
        case naming to add context.
        """
        if val == "":
            return "0 (null)"
        if val == "0":
            return "0 (1 limb)"

        if val[0] == "-":
            tmp = "negative"
            val = val[1:]
        else:
            tmp = "positive"
        if val[0] == "0":
            tmp += " with leading zero limb"
        elif len(val) > 10:
            tmp = "large " + tmp
        return tmp

    @classmethod
    def get_value_pairs(cls) -> Iterator[Tuple[str, str]]:
        """Generator to yield pairs of inputs.

        Combinations are first generated from all input values, and then
        specific cases provided.
        """
        yield from combination_pairs(cls.input_values)
        yield from cls.input_cases

    @classmethod
    def generate_function_tests(cls) -> Iterator[test_case.TestCase]:
        for a_value, b_value in cls.get_value_pairs():
            cur_op = cls(a_value, b_value)
            yield cur_op.create_test_case()


class BignumCmp(BignumOperation):
    """Test cases for bignum value comparison."""
    count = 0
    test_function = "mpi_cmp_mpi"
    test_name = "MPI compare"
    input_cases = [
        ("-2", "-3"),
        ("-2", "-2"),
        ("2b4", "2b5"),
        ("2b5", "2b6")
        ]

    def __init__(self, val_a, val_b) -> None:
        super().__init__(val_a, val_b)
        self._result = int(self.int_a > self.int_b) - int(self.int_a < self.int_b)
        self.symbol = ["<", "==", ">"][self._result + 1]

    def result(self) -> str:
        return str(self._result)


class BignumCmpAbs(BignumCmp):
    """Test cases for absolute bignum value comparison."""
    count = 0
    test_function = "mpi_cmp_abs"
    test_name = "MPI compare (abs)"

    def __init__(self, val_a, val_b) -> None:
        super().__init__(val_a.strip("-"), val_b.strip("-"))


class BignumAdd(BignumOperation):
    """Test cases for bignum value addition."""
    count = 0
    symbol = "+"
    test_function = "mpi_add_mpi"
    test_name = "MPI add"
    input_cases = combination_pairs(
        [
            "1c67967269c6", "9cde3",
            "-1c67967269c6", "-9cde3",
        ]
    )

    def result(self) -> str:
        return quote_str("{:x}".format(self.int_a + self.int_b))

if __name__ == '__main__':
    # Use the section of the docstring relevant to the CLI as description
    test_data_generation.main(sys.argv[1:], "\n".join(__doc__.splitlines()[:4]))
