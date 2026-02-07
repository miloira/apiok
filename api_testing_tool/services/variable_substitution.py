"""
Variable substitution service for replacing {{variable}} placeholders.

This service handles extraction and substitution of variable placeholders
in request templates (URL, headers, query params, body).
"""

import re
from typing import Tuple, List


# Pattern to match {{variable_name}} placeholders
VARIABLE_PATTERN = re.compile(r'\{\{(\w+)\}\}')


def extract_variables(template: str) -> List[str]:
    """
    Extract all variable names from a template string.
    
    Args:
        template: String containing {{variable}} placeholders
        
    Returns:
        List of variable names found in the template
        
    Example:
        >>> extract_variables("Hello {{name}}, your id is {{id}}")
        ['name', 'id']
    """
    if not template:
        return []
    
    return VARIABLE_PATTERN.findall(template)


def substitute(template: str, variables: dict[str, str]) -> Tuple[str, List[str]]:
    """
    Replace variable placeholders in a template with their values.
    
    Args:
        template: String containing {{variable}} placeholders
        variables: Dictionary mapping variable names to their values
        
    Returns:
        Tuple of (substituted string, list of unmatched variable names)
        
    Example:
        >>> substitute("Hello {{name}}", {"name": "World"})
        ('Hello World', [])
        >>> substitute("Hello {{name}}", {})
        ('Hello {{name}}', ['name'])
    """
    if not template:
        return template, []
    
    unmatched: List[str] = []
    
    def replace_match(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name in variables:
            return variables[var_name]
        else:
            unmatched.append(var_name)
            return match.group(0)  # Keep original placeholder
    
    result = VARIABLE_PATTERN.sub(replace_match, template)
    return result, unmatched


def substitute_dict(data: dict[str, str], variables: dict[str, str]) -> Tuple[dict[str, str], List[str]]:
    """
    Replace variable placeholders in all values of a dictionary.
    
    Args:
        data: Dictionary with string values that may contain placeholders
        variables: Dictionary mapping variable names to their values
        
    Returns:
        Tuple of (substituted dictionary, list of all unmatched variable names)
    """
    if not data:
        return data, []
    
    result = {}
    all_unmatched: List[str] = []
    
    for key, value in data.items():
        substituted_value, unmatched = substitute(value, variables)
        result[key] = substituted_value
        all_unmatched.extend(unmatched)
    
    return result, all_unmatched
