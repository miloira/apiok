"""
Property-based tests for the variable substitution service.

Tests Properties 10, 11, and 12 from the design document.
**Validates: Requirements 5.1, 5.2, 5.3**
"""

import pytest
from hypothesis import given, strategies as st, settings

from api_testing_tool.services.variable_substitution import (
    extract_variables,
    substitute,
)


# Strategy for generating valid variable names (alphanumeric + underscore)
variable_name_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"),
    min_size=1,
    max_size=20,
).filter(lambda s: s[0].isalpha() or s[0] == "_")  # Must start with letter or underscore

# Strategy for generating variable values
variable_value_strategy = st.text(min_size=0, max_size=100)


class TestProperty10VariablePlaceholderExtraction:
    """
    Property 10: 变量占位符提取
    
    *对于任意*包含 {{variable_name}} 格式占位符的字符串，
    变量提取函数应该返回所有变量名的列表。
    
    **Validates: Requirements 5.1**
    """

    @given(var_names=st.lists(variable_name_strategy, min_size=1, max_size=5, unique=True))
    @settings(max_examples=100)
    def test_extracts_all_variables_from_template(self, var_names: list[str]):
        """
        Property: For any template with {{variable}} placeholders,
        extract_variables should return all variable names.
        """
        # Build a template with all variable names
        template = " ".join("{{" + name + "}}" for name in var_names)
        
        extracted = extract_variables(template)
        
        # All variable names should be extracted
        assert set(extracted) == set(var_names)

    @given(text=st.text(min_size=0, max_size=100).filter(lambda s: "{{" not in s))
    @settings(max_examples=100)
    def test_returns_empty_for_no_placeholders(self, text: str):
        """
        Property: For any text without placeholders, extract_variables returns empty list.
        """
        extracted = extract_variables(text)
        assert extracted == []

    @given(var_name=variable_name_strategy, prefix=st.text(max_size=20), suffix=st.text(max_size=20))
    @settings(max_examples=100)
    def test_extracts_variable_regardless_of_surrounding_text(self, var_name: str, prefix: str, suffix: str):
        """
        Property: Variable extraction works regardless of surrounding text.
        """
        # Filter out any {{ or }} in prefix/suffix to avoid interference
        prefix = prefix.replace("{{", "").replace("}}", "")
        suffix = suffix.replace("{{", "").replace("}}", "")
        
        template = prefix + "{{" + var_name + "}}" + suffix
        
        extracted = extract_variables(template)
        assert var_name in extracted


class TestProperty11VariableSubstitutionCorrectness:
    """
    Property 11: 变量替换正确性
    
    *对于任意*包含占位符的模板字符串和变量映射，替换后的字符串中
    不应该包含已定义变量的占位符，且占位符位置应该被替换为对应的变量值。
    
    **Validates: Requirements 5.2**
    """

    @given(
        var_name=variable_name_strategy,
        var_value=variable_value_strategy.filter(lambda v: "{{" not in v and "}}" not in v)
    )
    @settings(max_examples=100)
    def test_defined_variable_is_replaced(self, var_name: str, var_value: str):
        """
        Property: A defined variable placeholder is replaced with its value.
        """
        template = "{{" + var_name + "}}"
        variables = {var_name: var_value}
        
        result, unmatched = substitute(template, variables)
        
        assert result == var_value
        assert unmatched == []

    @given(
        variables=st.dictionaries(
            keys=variable_name_strategy,
            values=variable_value_strategy.filter(lambda v: "{{" not in v and "}}" not in v),
            min_size=1,
            max_size=5
        )
    )
    @settings(max_examples=100)
    def test_all_defined_variables_are_replaced(self, variables: dict[str, str]):
        """
        Property: All defined variable placeholders are replaced with their values.
        """
        # Build template with all variables
        template = " ".join("{{" + name + "}}" for name in variables.keys())
        
        result, unmatched = substitute(template, variables)
        
        # No unmatched variables
        assert unmatched == []
        
        # Result should not contain any of the original placeholders
        for var_name in variables.keys():
            assert "{{" + var_name + "}}" not in result

    @given(
        var_name=variable_name_strategy,
        var_value=variable_value_strategy.filter(lambda v: "{{" not in v and "}}" not in v),
        prefix=st.text(max_size=20).filter(lambda s: "{{" not in s and "}}" not in s),
        suffix=st.text(max_size=20).filter(lambda s: "{{" not in s and "}}" not in s)
    )
    @settings(max_examples=100)
    def test_substitution_preserves_surrounding_text(self, var_name: str, var_value: str, prefix: str, suffix: str):
        """
        Property: Substitution replaces only the placeholder, preserving surrounding text.
        """
        template = prefix + "{{" + var_name + "}}" + suffix
        variables = {var_name: var_value}
        
        result, unmatched = substitute(template, variables)
        
        expected = prefix + var_value + suffix
        assert result == expected
        assert unmatched == []


class TestProperty12UndefinedVariablePreservation:
    """
    Property 12: 未定义变量保留
    
    *对于任意*包含未定义变量占位符的模板字符串，
    替换后该占位符应该保持原样，且应该返回警告信息。
    
    **Validates: Requirements 5.3**
    """

    @given(var_name=variable_name_strategy)
    @settings(max_examples=100)
    def test_undefined_variable_placeholder_is_preserved(self, var_name: str):
        """
        Property: An undefined variable placeholder is preserved in the output.
        """
        template = "{{" + var_name + "}}"
        variables = {}  # Empty - no variables defined
        
        result, unmatched = substitute(template, variables)
        
        # Placeholder should be preserved
        assert result == template
        # Variable name should be in unmatched list
        assert var_name in unmatched

    @given(
        defined_vars=st.dictionaries(
            keys=variable_name_strategy,
            values=variable_value_strategy.filter(lambda v: "{{" not in v and "}}" not in v),
            min_size=1,
            max_size=3
        ),
        undefined_var=variable_name_strategy
    )
    @settings(max_examples=100)
    def test_mixed_defined_and_undefined_variables(self, defined_vars: dict[str, str], undefined_var: str):
        """
        Property: When template has both defined and undefined variables,
        defined ones are replaced and undefined ones are preserved.
        """
        # Ensure undefined_var is not in defined_vars
        if undefined_var in defined_vars:
            return  # Skip this case
        
        # Build template with defined vars and one undefined var
        parts = ["{{" + name + "}}" for name in defined_vars.keys()]
        parts.append("{{" + undefined_var + "}}")
        template = " ".join(parts)
        
        result, unmatched = substitute(template, defined_vars)
        
        # Undefined variable should be in unmatched
        assert undefined_var in unmatched
        
        # Undefined placeholder should be preserved in result
        assert "{{" + undefined_var + "}}" in result
        
        # Defined placeholders should NOT be in result
        for var_name in defined_vars.keys():
            assert "{{" + var_name + "}}" not in result

    @given(undefined_vars=st.lists(variable_name_strategy, min_size=1, max_size=5, unique=True))
    @settings(max_examples=100)
    def test_all_undefined_variables_reported(self, undefined_vars: list[str]):
        """
        Property: All undefined variables are reported in the unmatched list.
        """
        template = " ".join("{{" + name + "}}" for name in undefined_vars)
        variables = {}  # No variables defined
        
        result, unmatched = substitute(template, variables)
        
        # All undefined variables should be reported
        assert set(unmatched) == set(undefined_vars)
