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

from functools import wraps
from typing import Any, Callable, Dict


def remove_attributes_with_null_values(attributes: Dict[str, Any]) -> Dict[str, Any]:
    return {attr: value for attr, value in attributes.items() if value is not None}


def attribute_generator(
    original_function: Callable[..., Dict[str, Any]],
) -> Callable[..., Dict[str, Any]]:
    @wraps(original_function)
    def wrapper(*args, **kwargs) -> Dict[str, Any]:
        attributes = original_function(*args, **kwargs)

        return remove_attributes_with_null_values(attributes)

    return wrapper

