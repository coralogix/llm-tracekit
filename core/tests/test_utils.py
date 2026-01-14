# Copyright Coralogix Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from llm_tracekit.core import (
    remove_attributes_with_null_values,
    attribute_generator,
)


def test_remove_attributes_with_null_values():
    """Test that null values are removed from attributes dict."""
    attributes = {
        "key1": "value1",
        "key2": None,
        "key3": "value3",
        "key4": None,
    }
    result = remove_attributes_with_null_values(attributes)
    
    assert result == {"key1": "value1", "key3": "value3"}


def test_remove_attributes_with_null_values_empty():
    """Test with empty dict."""
    assert remove_attributes_with_null_values({}) == {}


def test_remove_attributes_with_null_values_all_none():
    """Test with all None values."""
    attributes = {"key1": None, "key2": None}
    assert remove_attributes_with_null_values(attributes) == {}


def test_remove_attributes_with_null_values_no_none():
    """Test with no None values."""
    attributes = {"key1": "value1", "key2": "value2"}
    result = remove_attributes_with_null_values(attributes)
    assert result == attributes


def test_remove_attributes_preserves_falsy_values():
    """Test that falsy values (0, '', False) are preserved."""
    attributes = {
        "zero": 0,
        "empty_string": "",
        "false": False,
        "none": None,
    }
    result = remove_attributes_with_null_values(attributes)
    
    assert result == {"zero": 0, "empty_string": "", "false": False}


def test_attribute_generator_removes_none():
    """Test that attribute_generator decorator removes None values."""
    @attribute_generator
    def generate_attrs():
        return {"key1": "value1", "key2": None, "key3": "value3"}
    
    result = generate_attrs()
    assert result == {"key1": "value1", "key3": "value3"}


def test_attribute_generator_with_args():
    """Test attribute_generator with function arguments."""
    @attribute_generator
    def generate_attrs(value1, value2=None):
        return {"key1": value1, "key2": value2}
    
    result = generate_attrs("test")
    assert result == {"key1": "test"}
    
    result = generate_attrs("test", value2="value2")
    assert result == {"key1": "test", "key2": "value2"}
