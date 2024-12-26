"""Code analysis module for detecting potential logical errors and code quality issues."""

import ast
import re
from typing import Dict, List, Optional, Tuple

class CodeAnalyzer:
    def __init__(self):
        self.issues = []
        self.stats = {
            'complexity': 0,
            'nesting_depth': 0,
            'function_count': 0,
            'class_count': 0,
            'lines_of_code': 0,
            'comment_lines': 0
        }

    def analyze_file(self, file_path: str, content: str) -> Tuple[List[str], Dict]:
        """Analyze a file for potential logical errors and code quality issues."""
        self.issues = []
        self._reset_stats()
        
        # Basic file analysis
        self._analyze_basic_metrics(content)
        
        # Try parsing as Python
        try:
            tree = ast.parse(content)
            self._analyze_ast(tree)
        except SyntaxError:
            # If not Python, do pattern-based analysis
            self._analyze_patterns(content)
            
        return self.issues, self.stats

    def _reset_stats(self):
        """Reset statistics for new analysis."""
        self.stats = {
            'complexity': 0,
            'nesting_depth': 0,
            'function_count': 0,
            'class_count': 0,
            'lines_of_code': 0,
            'comment_lines': 0
        }

    def _analyze_basic_metrics(self, content: str):
        """Analyze basic code metrics."""
        lines = content.split('\n')
        self.stats['lines_of_code'] = len(lines)
        
        # Count comment lines
        comment_pattern = r'^\s*(#|//|/\*|\*|<!--)'
        self.stats['comment_lines'] = sum(1 for line in lines if re.match(comment_pattern, line))
        
        # Calculate nesting depth
        max_indent = 0
        for line in lines:
            indent = len(line) - len(line.lstrip())
            max_indent = max(max_indent, indent)
        self.stats['nesting_depth'] = max_indent // 4  # Assuming 4 spaces per indent level

    def _analyze_ast(self, tree: ast.AST):
        """Analyze Python AST for potential issues."""
        class ASTAnalyzer(ast.NodeVisitor):
            def __init__(self, analyzer):
                self.analyzer = analyzer
                self.current_complexity = 0
                
            def visit_FunctionDef(self, node):
                self.analyzer.stats['function_count'] += 1
                
                # Check function complexity
                if len(node.body) > 20:
                    self.analyzer.issues.append(
                        f"Function '{node.name}' is too long ({len(node.body)} lines)"
                    )
                
                # Check number of arguments
                if len(node.args.args) > 5:
                    self.analyzer.issues.append(
                        f"Function '{node.name}' has too many parameters ({len(node.args.args)})"
                    )
                
                self.generic_visit(node)
                
            def visit_ClassDef(self, node):
                self.analyzer.stats['class_count'] += 1
                
                # Check class complexity
                if len(node.body) > 30:
                    self.analyzer.issues.append(
                        f"Class '{node.name}' might be too complex ({len(node.body)} members)"
                    )
                
                self.generic_visit(node)
                
            def visit_If(self, node):
                self.current_complexity += 1
                self.generic_visit(node)
                
            def visit_While(self, node):
                self.current_complexity += 1
                self.generic_visit(node)
                
            def visit_For(self, node):
                self.current_complexity += 1
                self.generic_visit(node)
                
            def visit_Try(self, node):
                if len(node.handlers) > 2:
                    self.analyzer.issues.append(
                        "Try block has too many except clauses"
                    )
                self.generic_visit(node)
        
        analyzer = ASTAnalyzer(self)
        analyzer.visit(tree)
        self.stats['complexity'] = analyzer.current_complexity

    def _analyze_patterns(self, content: str):
        """Analyze code using pattern matching for non-Python files."""
        # Check for hardcoded values
        if re.search(r'(password|secret|key)\s*=\s*["\'][^"\']+["\']', content, re.I):
            self.issues.append("Possible hardcoded credentials detected")
            
        # Check for TODO comments
        if re.search(r'(TODO|FIXME|XXX|HACK):', content):
            self.issues.append("Contains TODO/FIXME comments that need attention")
            
        # Check for long lines
        long_lines = [i+1 for i, line in enumerate(content.split('\n')) if len(line) > 100]
        if long_lines:
            self.issues.append(f"Lines {', '.join(map(str, long_lines))} exceed recommended length")
            
        # Check for nested callbacks (JavaScript/TypeScript)
        if content.count('=>') > 3:
            nested_callbacks = content.count('=>')
            if nested_callbacks > 5:
                self.issues.append(f"High number of nested callbacks/promises ({nested_callbacks})")
                
        # Estimate complexity based on control structures
        control_structures = len(re.findall(r'\b(if|for|while|switch)\b', content))
        self.stats['complexity'] = control_structures 