# Copyright (c) Microsoft. All rights reserved.

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from semantic_kernel import Kernel
from semantic_kernel.data.text_search import (
    DEFAULT_DESCRIPTION,
    DEFAULT_FUNCTION_NAME,
    KernelSearchResults,
    SearchOptions,
    TextSearch,
    TextSearchResult,
    create_options,
)
from semantic_kernel.data.vector import VectorSearchOptions
from semantic_kernel.exceptions import TextSearchException
from semantic_kernel.functions import KernelArguments, KernelParameterMetadata
from semantic_kernel.utils.list_handler import desync_list


def test_text_search():
    search_base_class = TextSearch()
    assert search_base_class is not None
    assert search_base_class.options_class == SearchOptions


class TestSearch(TextSearch):
    async def search(self, **kwargs) -> KernelSearchResults[Any]:
        """Test search function."""
        output_type = kwargs.pop("output_type", str)

        async def generator() -> AsyncGenerator[str | TextSearchResult | Any, None]:
            yield "test" if output_type is not TextSearchResult else TextSearchResult(value="test")

        return KernelSearchResults(results=generator(), metadata=kwargs)


@pytest.mark.parametrize("output_type", [str, TextSearchResult, "Any"])
async def test_create_kernel_function(output_type: str, kernel: Kernel):
    test_search = TestSearch()
    kernel_function = test_search._create_kernel_function(output_type=output_type)
    assert kernel_function is not None
    assert kernel_function.name == DEFAULT_FUNCTION_NAME
    assert kernel_function.description == DEFAULT_DESCRIPTION
    assert len(kernel_function.parameters) == 3
    assert kernel_function.return_parameter == KernelParameterMetadata(
        name="results",
        description="The search results.",
        type="list[str]",
        type_object=list,
        is_required=True,
    )
    results = await kernel_function.invoke(kernel, KernelArguments(query="query"))
    assert results is not None
    assert results.value == (
        ['{"name":null,"value":"test","link":null}'] if output_type is TextSearchResult else ["test"]
    )


def test_create_kernel_function_fail():
    test_search = TestSearch()
    with pytest.raises(TextSearchException):
        test_search.create_search_function(
            function_name="search",
            description="description",
            output_type="random",
            parameters=None,
            return_parameter=None,
            string_mapper=None,
        )


async def test_create_kernel_function_inner(kernel: Kernel):
    test_search = TestSearch()

    kernel_function = test_search._create_kernel_function(
        output_type=str,
        options=None,
        parameters=[],
        return_parameter=None,
        function_name="search",
        description="description",
        string_mapper=None,
    )
    results = await kernel_function.invoke(kernel, None)
    assert results is not None
    assert results.value == ["test"]


async def test_create_kernel_function_inner_with_options(kernel: Kernel):
    test_search = TestSearch()

    kernel_function = test_search._create_kernel_function(
        output_type=str,
        options=SearchOptions(),
        parameters=[
            KernelParameterMetadata(
                name="city",
                description="The city that you want to search for a hotel in.",
                type="str",
                is_required=False,
                type_object=str,
            )
        ],
        return_parameter=None,
        function_name="search",
        description="description",
        string_mapper=None,
    )
    results = await kernel_function.invoke(kernel, KernelArguments(city="city"))
    assert results is not None
    assert results.value == ["test"]


async def test_create_kernel_function_inner_with_other_options_type(kernel: Kernel):
    test_search = TestSearch()

    kernel_function = test_search._create_kernel_function(
        output_type=str,
        options=VectorSearchOptions(),
        parameters=[
            KernelParameterMetadata(
                name="test_field",
                description="The test field.",
                type="str",
                is_required=False,
                type_object=str,
            )
        ],
        return_parameter=None,
        function_name="search",
        description="description",
        string_mapper=None,
    )
    results = await kernel_function.invoke(kernel, KernelArguments(test_field="city"))
    assert results is not None
    assert results.value == ["test"]


async def test_create_kernel_function_inner_no_results(kernel: Kernel):
    test_search = TestSearch()

    kernel_function = test_search._create_kernel_function(
        output_type=str,
        options=None,
        parameters=[],
        return_parameter=None,
        function_name="search",
        description="description",
        string_mapper=None,
    )
    with (
        patch.object(test_search, "search") as mock_search,
        pytest.raises(TextSearchException),
    ):
        mock_search.side_effect = Exception("fail")
        await kernel_function.invoke(kernel, None)


async def test_default_map_to_string():
    test_search = TestSearch()
    assert (await test_search._map_results(results=KernelSearchResults(results=desync_list(["test"])))) == ["test"]

    class TestClass(BaseModel):
        test: str

    assert (
        await test_search._map_results(results=KernelSearchResults(results=desync_list([TestClass(test="test")])))
    ) == ['{"test":"test"}']


async def test_custom_map_to_string():
    test_search = TestSearch()

    class TestClass(BaseModel):
        test: str

    assert (
        await test_search._map_results(
            results=KernelSearchResults(results=desync_list([TestClass(test="test")])), string_mapper=lambda x: x.test
        )
    ) == ["test"]


def test_create_options():
    options = SearchOptions()
    options_class = VectorSearchOptions
    new_options = create_options(options_class, options, top=1)
    assert new_options is not None
    assert isinstance(new_options, options_class)
    assert new_options.top == 1


def test_create_options_none():
    options = None
    options_class = VectorSearchOptions
    new_options = create_options(options_class, options, top=1)
    assert new_options is not None
    assert isinstance(new_options, options_class)
    assert new_options.top == 1


def test_create_options_from_dict():
    options = {"skip": 1}
    options_class = SearchOptions
    new_options = create_options(options_class, options, top=1)  # type: ignore
    assert new_options is not None
    assert isinstance(new_options, options_class)
    assert new_options.top == 1
    # if a non SearchOptions object is passed in, it should be ignored
    assert new_options.skip == 0


def test_public_create_functions_search():
    test_search = TestSearch()
    function = test_search.create_search_function()
    assert function is not None
    assert function.name == "search"
    assert (
        function.description == "Perform a search for content related to the specified query and return string results"
    )
    assert len(function.parameters) == 3
