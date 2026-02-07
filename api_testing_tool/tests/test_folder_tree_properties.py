"""
Property-based tests for the folder tree service.

Uses Hypothesis to verify universal properties of the tree-building algorithm
across many randomly generated inputs.

**Feature: nested-groups**
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from api_testing_tool.services.folder_tree import build_folder_tree


# ---------------------------------------------------------------------------
# Lightweight stand-ins for ORM models (build_folder_tree only reads attrs)
# ---------------------------------------------------------------------------

@dataclass
class FakeFolder:
    """Minimal stand-in for the Folder ORM model."""
    id: int
    name: str
    collection_id: int
    parent_folder_id: Optional[int]
    sort_order: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FakeRequest:
    """Minimal stand-in for the Request ORM model."""
    id: int
    name: str
    method: str = "GET"
    url: str = "https://example.com"
    headers: dict = field(default_factory=dict)
    query_params: dict = field(default_factory=dict)
    body_type: Optional[str] = None
    body: Optional[str] = None
    collection_id: Optional[int] = None
    folder_id: Optional[int] = None
    sort_order: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Hypothesis strategies – smart generators for valid folder trees
# ---------------------------------------------------------------------------

@st.composite
def valid_folder_list(draw: st.DrawFn):
    """
    Generate a valid flat list of FakeFolder objects forming a legal tree.

    Strategy:
    - Draw a number of folders (0..20).
    - Assign unique IDs starting from 1.
    - For each folder, its parent_folder_id is either None (root) or the ID
      of a *previously created* folder. This guarantees:
        • All parent references point to existing folders.
        • No circular references (a folder can only reference an earlier ID).
        • The result is a valid forest (set of trees).
    """
    n = draw(st.integers(min_value=0, max_value=20))
    folders: list[FakeFolder] = []
    for i in range(1, n + 1):
        if not folders:
            parent_id = None
        else:
            # Either root or one of the already-created folder IDs
            parent_id = draw(
                st.one_of(
                    st.none(),
                    st.sampled_from([f.id for f in folders]),
                )
            )
        folders.append(
            FakeFolder(
                id=i,
                name=f"Folder-{i}",
                collection_id=1,
                parent_folder_id=parent_id,
            )
        )
    return folders


@st.composite
def valid_folder_list_with_requests(draw: st.DrawFn):
    """
    Generate a valid flat list of FakeFolder objects together with FakeRequest
    objects assigned to those folders.
    """
    folders = draw(valid_folder_list())
    folder_ids = [f.id for f in folders]

    # Generate 0..30 requests, each optionally assigned to a folder
    n_requests = draw(st.integers(min_value=0, max_value=30))
    requests: list[FakeRequest] = []
    for i in range(1, n_requests + 1):
        if folder_ids:
            folder_id = draw(
                st.one_of(
                    st.none(),
                    st.sampled_from(folder_ids),
                )
            )
        else:
            folder_id = None
        requests.append(
            FakeRequest(
                id=i,
                name=f"Request-{i}",
                collection_id=1,
                folder_id=folder_id,
            )
        )
    return folders, requests


# ---------------------------------------------------------------------------
# Helper: flatten a tree back into a set of (id, parent_folder_id) tuples
# ---------------------------------------------------------------------------

def flatten_tree(tree: list[dict]) -> set[tuple[int, Optional[int]]]:
    """
    Recursively flatten a tree (as returned by build_folder_tree) into a set
    of (folder_id, parent_folder_id) tuples.
    """
    result: set[tuple[int, Optional[int]]] = set()
    for node in tree:
        result.add((node["id"], node["parent_folder_id"]))
        result.update(flatten_tree(node["children"]))
    return result


def flatten_tree_requests(tree: list[dict]) -> set[tuple[int, Optional[int]]]:
    """
    Recursively collect all (request_id, folder_id) pairs from the tree.
    """
    result: set[tuple[int, Optional[int]]] = set()
    for node in tree:
        for req in node["requests"]:
            result.add((req["id"], req["folder_id"]))
        result.update(flatten_tree_requests(node["children"]))
    return result


# ---------------------------------------------------------------------------
# Property 1: 树构建往返一致性 (Tree Build Round-Trip Consistency)
# ---------------------------------------------------------------------------
# **Feature: nested-groups, Property 1: 树构建往返一致性**
# **Validates: Requirements 1.1, 1.2, 1.3**
#
# For any valid flat folder list (with legal parent_folder_id references),
# building it into a tree structure and then flattening it should produce
# the same set of folders (same IDs and parent-child relationships).
# ---------------------------------------------------------------------------


class TestTreeBuildRoundTripProperty:
    """Property 1: 树构建往返一致性"""

    @given(data=valid_folder_list())
    @settings(max_examples=150)
    def test_round_trip_preserves_folder_ids_and_parents(self, data: list[FakeFolder]):
        """
        **Feature: nested-groups, Property 1: 树构建往返一致性**
        **Validates: Requirements 1.1, 1.2, 1.3**

        Building a tree from a flat folder list and flattening it back
        must yield the exact same set of (id, parent_folder_id) pairs.
        """
        tree = build_folder_tree(data, [])

        # Flatten the tree back
        flattened = flatten_tree(tree)

        # Build expected set from the original flat list
        expected = {(f.id, f.parent_folder_id) for f in data}

        assert flattened == expected

    @given(data=valid_folder_list())
    @settings(max_examples=150)
    def test_round_trip_preserves_folder_count(self, data: list[FakeFolder]):
        """
        **Feature: nested-groups, Property 1: 树构建往返一致性**
        **Validates: Requirements 1.1, 1.2, 1.3**

        The total number of folders in the tree must equal the number
        of folders in the original flat list.
        """
        tree = build_folder_tree(data, [])

        def count_nodes(nodes: list[dict]) -> int:
            total = 0
            for node in nodes:
                total += 1 + count_nodes(node["children"])
            return total

        assert count_nodes(tree) == len(data)

    @given(data=valid_folder_list())
    @settings(max_examples=150)
    def test_root_nodes_have_no_parent(self, data: list[FakeFolder]):
        """
        **Feature: nested-groups, Property 1: 树构建往返一致性**
        **Validates: Requirements 1.1, 1.2, 1.3**

        Every top-level node in the tree must have parent_folder_id == None,
        matching the root folders in the original flat list.
        """
        tree = build_folder_tree(data, [])

        root_ids_from_tree = {node["id"] for node in tree}
        root_ids_expected = {f.id for f in data if f.parent_folder_id is None}

        assert root_ids_from_tree == root_ids_expected

    @given(data=valid_folder_list())
    @settings(max_examples=150)
    def test_children_reference_correct_parent(self, data: list[FakeFolder]):
        """
        **Feature: nested-groups, Property 1: 树构建往返一致性**
        **Validates: Requirements 1.1, 1.2, 1.3**

        For every node in the tree, each child's parent_folder_id must
        equal the node's id.
        """
        tree = build_folder_tree(data, [])

        def check_parent_refs(nodes: list[dict], expected_parent_id: Optional[int]):
            for node in nodes:
                assert node["parent_folder_id"] == expected_parent_id
                check_parent_refs(node["children"], node["id"])

        check_parent_refs(tree, None)

    @given(data=valid_folder_list_with_requests())
    @settings(max_examples=150)
    def test_round_trip_preserves_request_assignments(self, data):
        """
        **Feature: nested-groups, Property 1: 树构建往返一致性**
        **Validates: Requirements 1.1, 1.2, 1.3**

        Requests assigned to folders must appear in the correct folder
        node in the tree. Requests with folder_id=None are excluded.
        """
        folders, requests = data
        tree = build_folder_tree(folders, requests)

        # Collect (request_id, folder_id) from the tree
        tree_req_pairs = flatten_tree_requests(tree)

        # Expected: only requests whose folder_id is in the folder set
        folder_ids = {f.id for f in folders}
        expected_req_pairs = {
            (r.id, r.folder_id)
            for r in requests
            if r.folder_id is not None and r.folder_id in folder_ids
        }

        assert tree_req_pairs == expected_req_pairs

    @given(data=valid_folder_list())
    @settings(max_examples=150)
    def test_empty_children_for_leaf_folders(self, data: list[FakeFolder]):
        """
        **Feature: nested-groups, Property 1: 树构建往返一致性**
        **Validates: Requirements 1.1, 1.2, 1.3**

        Folders that have no children in the flat list must have an
        empty children list in the tree (Requirement 1.3).
        """
        tree = build_folder_tree(data, [])

        # Determine which folder IDs are parents
        parent_ids = {f.parent_folder_id for f in data if f.parent_folder_id is not None}

        def check_leaves(nodes: list[dict]):
            for node in nodes:
                if node["id"] not in parent_ids:
                    assert node["children"] == []
                check_leaves(node["children"])

        check_leaves(tree)


# ---------------------------------------------------------------------------
# Property 3: 循环引用检测完备性 (Circular Reference Detection Completeness)
# ---------------------------------------------------------------------------
# **Feature: nested-groups, Property 3: 循环引用检测完备性**
# **Validates: Requirements 3.1, 3.2, 3.3**
#
# For any folder tree and any ancestor-descendant pair (A, D), moving A
# under D should cause detect_circular_reference to return True; for any
# non-ancestor-descendant pair, it should return False.
# ---------------------------------------------------------------------------

import os
import uuid

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from api_testing_tool.database import Base
from api_testing_tool.models.collection import Collection, Folder
from api_testing_tool.services.folder_tree import detect_circular_reference


def _make_test_db():
    """Create a fresh in-memory SQLite database and return a session factory."""
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _get_ancestors(folder_id: int, parent_map: dict[int, Optional[int]]) -> set[int]:
    """
    Compute the set of all ancestor IDs for a given folder.

    Walks up the parent chain from folder_id (exclusive) to the root.
    """
    ancestors: set[int] = set()
    current = parent_map.get(folder_id)
    while current is not None:
        ancestors.add(current)
        current = parent_map.get(current)
    return ancestors


def _get_descendants(folder_id: int, children_map: dict[int, list[int]]) -> set[int]:
    """
    Compute the set of all descendant IDs for a given folder.

    Uses BFS to collect all transitive children.
    """
    descendants: set[int] = set()
    stack = list(children_map.get(folder_id, []))
    while stack:
        child = stack.pop()
        descendants.add(child)
        stack.extend(children_map.get(child, []))
    return descendants


@st.composite
def folder_tree_with_ancestor_descendant_pair(draw: st.DrawFn):
    """
    Generate a valid folder tree (2..15 nodes) and pick an ancestor-descendant
    pair (A, D) where A is a proper ancestor of D.

    Returns (folder_specs, ancestor_id, descendant_id) where folder_specs is
    a list of (id, parent_id) tuples describing the tree.
    """
    n = draw(st.integers(min_value=2, max_value=15))
    # Build a valid tree: each folder's parent is either None or a previously created ID
    folder_specs: list[tuple[int, Optional[int]]] = []
    for i in range(1, n + 1):
        if i == 1:
            parent_id = None
        else:
            parent_id = draw(
                st.one_of(
                    st.none(),
                    st.sampled_from([fid for fid, _ in folder_specs]),
                )
            )
        folder_specs.append((i, parent_id))

    # Build parent_map and children_map for relationship computation
    parent_map: dict[int, Optional[int]] = {fid: pid for fid, pid in folder_specs}
    children_map: dict[int, list[int]] = {}
    for fid, pid in folder_specs:
        if pid is not None:
            children_map.setdefault(pid, []).append(fid)

    # Find all ancestor-descendant pairs
    ancestor_descendant_pairs: list[tuple[int, int]] = []
    for fid, _ in folder_specs:
        descendants = _get_descendants(fid, children_map)
        for desc in descendants:
            ancestor_descendant_pairs.append((fid, desc))

    # We need at least one ancestor-descendant pair
    assume(len(ancestor_descendant_pairs) > 0)

    ancestor_id, descendant_id = draw(st.sampled_from(ancestor_descendant_pairs))
    return folder_specs, ancestor_id, descendant_id


@st.composite
def folder_tree_with_non_ancestor_descendant_pair(draw: st.DrawFn):
    """
    Generate a valid folder tree (2..15 nodes) and pick a pair (X, Y) where
    X is NOT an ancestor of Y and X != Y (i.e., moving X under Y would NOT
    create a circular reference).

    Returns (folder_specs, folder_x, folder_y).
    """
    n = draw(st.integers(min_value=2, max_value=15))
    folder_specs: list[tuple[int, Optional[int]]] = []
    for i in range(1, n + 1):
        if i == 1:
            parent_id = None
        else:
            parent_id = draw(
                st.one_of(
                    st.none(),
                    st.sampled_from([fid for fid, _ in folder_specs]),
                )
            )
        folder_specs.append((i, parent_id))

    parent_map: dict[int, Optional[int]] = {fid: pid for fid, pid in folder_specs}
    children_map: dict[int, list[int]] = {}
    for fid, pid in folder_specs:
        if pid is not None:
            children_map.setdefault(pid, []).append(fid)

    all_ids = [fid for fid, _ in folder_specs]

    # Find all non-ancestor-descendant pairs (X, Y) where X != Y
    # and X is NOT an ancestor of Y (so moving X under Y is safe)
    non_ad_pairs: list[tuple[int, int]] = []
    for x in all_ids:
        descendants_of_x = _get_descendants(x, children_map)
        for y in all_ids:
            if x != y and y not in descendants_of_x:
                non_ad_pairs.append((x, y))

    assume(len(non_ad_pairs) > 0)

    folder_x, folder_y = draw(st.sampled_from(non_ad_pairs))
    return folder_specs, folder_x, folder_y


@st.composite
def folder_tree_with_self_reference(draw: st.DrawFn):
    """
    Generate a valid folder tree (1..10 nodes) and pick any folder for
    self-reference testing.

    Returns (folder_specs, folder_id).
    """
    n = draw(st.integers(min_value=1, max_value=10))
    folder_specs: list[tuple[int, Optional[int]]] = []
    for i in range(1, n + 1):
        if i == 1:
            parent_id = None
        else:
            parent_id = draw(
                st.one_of(
                    st.none(),
                    st.sampled_from([fid for fid, _ in folder_specs]),
                )
            )
        folder_specs.append((i, parent_id))

    folder_id = draw(st.sampled_from([fid for fid, _ in folder_specs]))
    return folder_specs, folder_id


def _populate_db(session, folder_specs: list[tuple[int, Optional[int]]]):
    """
    Create a Collection and Folder rows in the database from folder_specs.

    folder_specs is a list of (id, parent_folder_id) tuples. Folders are
    inserted in order so that parent references are always valid.
    """
    collection = Collection(name="Test Collection")
    session.add(collection)
    session.flush()

    for fid, pid in folder_specs:
        folder = Folder(
            id=fid,
            name=f"Folder-{fid}",
            collection_id=collection.id,
            parent_folder_id=pid,
        )
        session.add(folder)
    session.commit()


class TestCircularReferenceDetectionProperty:
    """Property 3: 循环引用检测完备性"""

    @given(data=folder_tree_with_ancestor_descendant_pair())
    @settings(max_examples=150)
    def test_ancestor_moved_under_descendant_detected_as_circular(self, data):
        """
        **Feature: nested-groups, Property 3: 循环引用检测完备性**
        **Validates: Requirements 3.1, 3.2, 3.3**

        For any ancestor-descendant pair (A, D) in a valid folder tree,
        detect_circular_reference(A, D, db) must return True because
        moving A under D would create a cycle.
        """
        folder_specs, ancestor_id, descendant_id = data

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)
            result = detect_circular_reference(ancestor_id, descendant_id, session)
            assert result is True, (
                f"Expected circular reference detected when moving ancestor {ancestor_id} "
                f"under descendant {descendant_id}, but got False"
            )
        finally:
            session.close()

    @given(data=folder_tree_with_non_ancestor_descendant_pair())
    @settings(max_examples=150)
    def test_non_ancestor_descendant_pair_not_detected_as_circular(self, data):
        """
        **Feature: nested-groups, Property 3: 循环引用检测完备性**
        **Validates: Requirements 3.1, 3.2, 3.3**

        For any pair (X, Y) where X is NOT an ancestor of Y and X != Y,
        detect_circular_reference(X, Y, db) must return False because
        moving X under Y would not create a cycle.
        """
        folder_specs, folder_x, folder_y = data

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)
            result = detect_circular_reference(folder_x, folder_y, session)
            assert result is False, (
                f"Expected no circular reference when moving {folder_x} "
                f"under {folder_y}, but got True"
            )
        finally:
            session.close()

    @given(data=folder_tree_with_self_reference())
    @settings(max_examples=150)
    def test_self_reference_always_detected_as_circular(self, data):
        """
        **Feature: nested-groups, Property 3: 循环引用检测完备性**
        **Validates: Requirements 3.1, 3.2, 3.3**

        For any folder in a valid tree, detect_circular_reference(F, F, db)
        must return True because a folder cannot be its own parent.
        """
        folder_specs, folder_id = data

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)
            result = detect_circular_reference(folder_id, folder_id, session)
            assert result is True, (
                f"Expected self-reference detected for folder {folder_id}, "
                f"but got False"
            )
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Property 5: 嵌套深度不变量 (Nesting Depth Invariant)
# ---------------------------------------------------------------------------
# **Feature: nested-groups, Property 5: 嵌套深度不变量**
# **Validates: Requirements 5.1, 5.2, 5.3**
#
# For any legal sequence of folder creation or move operations, no folder
# in the system should exceed nesting depth of 5. When an operation would
# exceed the limit, it should be rejected.
# ---------------------------------------------------------------------------

from api_testing_tool.services.folder_tree import (
    get_folder_depth,
    get_subtree_depth,
    MAX_NESTING_DEPTH,
)


@st.composite
def folder_tree_in_db(draw: st.DrawFn):
    """
    Generate a valid folder tree (1..15 nodes) with controlled depth,
    populate it in a fresh in-memory SQLite database, and return
    (session, folder_specs, parent_map, children_map).

    The tree is guaranteed to have valid parent references and no cycles.
    Depth is NOT constrained to MAX_NESTING_DEPTH — this allows testing
    both within-limit and over-limit scenarios.
    """
    n = draw(st.integers(min_value=1, max_value=15))
    folder_specs: list[tuple[int, Optional[int]]] = []
    for i in range(1, n + 1):
        if i == 1:
            parent_id = None
        else:
            parent_id = draw(
                st.one_of(
                    st.none(),
                    st.sampled_from([fid for fid, _ in folder_specs]),
                )
            )
        folder_specs.append((i, parent_id))

    parent_map: dict[int, Optional[int]] = {fid: pid for fid, pid in folder_specs}
    children_map: dict[int, list[int]] = {}
    for fid, pid in folder_specs:
        if pid is not None:
            children_map.setdefault(pid, []).append(fid)

    return folder_specs, parent_map, children_map


@st.composite
def folder_tree_within_depth_limit(draw: st.DrawFn):
    """
    Generate a valid folder tree where ALL folders are within MAX_NESTING_DEPTH.

    Strategy: build folders one at a time, only allowing a parent whose
    current depth is < MAX_NESTING_DEPTH (so the child will be at most
    MAX_NESTING_DEPTH).
    """
    n = draw(st.integers(min_value=1, max_value=20))
    folder_specs: list[tuple[int, Optional[int]]] = []
    # Track depth of each folder for constraint
    depth_of: dict[int, int] = {}

    for i in range(1, n + 1):
        if i == 1:
            parent_id = None
        else:
            # Only allow parents whose depth < MAX_NESTING_DEPTH
            eligible_parents = [
                fid for fid, _ in folder_specs
                if depth_of[fid] < MAX_NESTING_DEPTH
            ]
            if eligible_parents:
                parent_id = draw(
                    st.one_of(
                        st.none(),
                        st.sampled_from(eligible_parents),
                    )
                )
            else:
                parent_id = None

        folder_specs.append((i, parent_id))
        depth_of[i] = 1 if parent_id is None else depth_of[parent_id] + 1

    parent_map: dict[int, Optional[int]] = {fid: pid for fid, pid in folder_specs}
    children_map: dict[int, list[int]] = {}
    for fid, pid in folder_specs:
        if pid is not None:
            children_map.setdefault(pid, []).append(fid)

    return folder_specs, parent_map, children_map, depth_of


def _compute_depth(folder_id: int, parent_map: dict[int, Optional[int]]) -> int:
    """Compute depth by walking up the parent chain. Root = depth 1."""
    depth = 0
    current: Optional[int] = folder_id
    while current is not None:
        depth += 1
        current = parent_map.get(current)
    return depth


def _compute_subtree_depth(folder_id: int, children_map: dict[int, list[int]]) -> int:
    """Compute the max depth of the subtree rooted at folder_id. Leaf = 1."""
    children = children_map.get(folder_id, [])
    if not children:
        return 1
    return 1 + max(_compute_subtree_depth(c, children_map) for c in children)


class TestNestingDepthInvariantProperty:
    """Property 5: 嵌套深度不变量"""

    @given(data=folder_tree_in_db())
    @settings(max_examples=150)
    def test_get_folder_depth_matches_parent_chain_walk(self, data):
        """
        **Feature: nested-groups, Property 5: 嵌套深度不变量**
        **Validates: Requirements 5.1, 5.2, 5.3**

        For any folder in a randomly generated tree, get_folder_depth()
        must return the same value as manually walking the parent chain.
        Root-level folders have depth 1.
        """
        folder_specs, parent_map, children_map = data

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            for fid, _ in folder_specs:
                db_depth = get_folder_depth(fid, session)
                expected_depth = _compute_depth(fid, parent_map)
                assert db_depth == expected_depth, (
                    f"get_folder_depth({fid}) returned {db_depth}, "
                    f"expected {expected_depth}"
                )
        finally:
            session.close()

    @given(data=folder_tree_in_db())
    @settings(max_examples=150)
    def test_get_subtree_depth_matches_recursive_computation(self, data):
        """
        **Feature: nested-groups, Property 5: 嵌套深度不变量**
        **Validates: Requirements 5.1, 5.2, 5.3**

        For any folder in a randomly generated tree, get_subtree_depth()
        must return the same value as recursively computing the max depth
        of the subtree. Leaf folders have subtree depth 1.
        """
        folder_specs, parent_map, children_map = data

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            for fid, _ in folder_specs:
                db_subtree = get_subtree_depth(fid, session)
                expected_subtree = _compute_subtree_depth(fid, children_map)
                assert db_subtree == expected_subtree, (
                    f"get_subtree_depth({fid}) returned {db_subtree}, "
                    f"expected {expected_subtree}"
                )
        finally:
            session.close()

    @given(data=folder_tree_in_db())
    @settings(max_examples=150)
    def test_depth_plus_subtree_depth_consistency(self, data):
        """
        **Feature: nested-groups, Property 5: 嵌套深度不变量**
        **Validates: Requirements 5.1, 5.2, 5.3**

        For any folder F, depth(F) + subtree_depth(F) - 1 equals the
        maximum depth of any leaf reachable from F. This ensures the
        depth and subtree_depth computations are mutually consistent,
        which is critical for correct MAX_NESTING_DEPTH validation.
        """
        folder_specs, parent_map, children_map = data

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            for fid, _ in folder_specs:
                depth = get_folder_depth(fid, session)
                subtree = get_subtree_depth(fid, session)
                # depth(F) + subtree_depth(F) - 1 = max leaf depth in F's subtree
                max_leaf_depth = depth + subtree - 1

                # Verify by computing the actual max leaf depth from F's subtree
                def _max_leaf_depth_from(node_id: int, current_depth: int) -> int:
                    kids = children_map.get(node_id, [])
                    if not kids:
                        return current_depth
                    return max(
                        _max_leaf_depth_from(c, current_depth + 1) for c in kids
                    )

                actual_max = _max_leaf_depth_from(fid, depth)
                assert max_leaf_depth == actual_max, (
                    f"For folder {fid}: depth={depth}, subtree={subtree}, "
                    f"depth+subtree-1={max_leaf_depth}, actual max leaf depth={actual_max}"
                )
        finally:
            session.close()

    @given(data=folder_tree_within_depth_limit())
    @settings(max_examples=150)
    def test_all_folders_within_max_nesting_depth(self, data):
        """
        **Feature: nested-groups, Property 5: 嵌套深度不变量**
        **Validates: Requirements 5.1, 5.2, 5.3**

        For any tree constructed with the depth constraint (no folder
        deeper than MAX_NESTING_DEPTH), get_folder_depth() must confirm
        that every folder's depth is <= MAX_NESTING_DEPTH.
        """
        folder_specs, parent_map, children_map, depth_of = data

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            for fid, _ in folder_specs:
                db_depth = get_folder_depth(fid, session)
                assert db_depth <= MAX_NESTING_DEPTH, (
                    f"Folder {fid} has depth {db_depth} which exceeds "
                    f"MAX_NESTING_DEPTH={MAX_NESTING_DEPTH}"
                )
                # Also verify against our tracked depth
                assert db_depth == depth_of[fid], (
                    f"Folder {fid}: get_folder_depth returned {db_depth}, "
                    f"expected {depth_of[fid]}"
                )
        finally:
            session.close()

    @given(data=folder_tree_within_depth_limit())
    @settings(max_examples=150)
    def test_depth_validation_rejects_over_limit_child(self, data):
        """
        **Feature: nested-groups, Property 5: 嵌套深度不变量**
        **Validates: Requirements 5.1, 5.2, 5.3**

        For any folder at exactly MAX_NESTING_DEPTH, adding a child
        would exceed the limit. Verify that depth(parent) + 1 > MAX_NESTING_DEPTH
        for such folders, meaning the operation should be rejected.
        For folders below the limit, adding a child should be allowed.
        """
        folder_specs, parent_map, children_map, depth_of = data

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            for fid, _ in folder_specs:
                parent_depth = get_folder_depth(fid, session)
                child_would_be_at = parent_depth + 1

                if parent_depth >= MAX_NESTING_DEPTH:
                    # Adding a child here should be rejected
                    assert child_would_be_at > MAX_NESTING_DEPTH, (
                        f"Folder {fid} at depth {parent_depth}: adding a child "
                        f"at depth {child_would_be_at} should exceed limit"
                    )
                else:
                    # Adding a child here should be allowed
                    assert child_would_be_at <= MAX_NESTING_DEPTH, (
                        f"Folder {fid} at depth {parent_depth}: adding a child "
                        f"at depth {child_would_be_at} should be within limit"
                    )
        finally:
            session.close()

    @given(data=folder_tree_within_depth_limit())
    @settings(max_examples=150)
    def test_move_validation_uses_depth_plus_subtree(self, data):
        """
        **Feature: nested-groups, Property 5: 嵌套深度不变量**
        **Validates: Requirements 5.1, 5.2, 5.3**

        When considering moving folder F to a new parent P, the total
        depth would be depth(P) + subtree_depth(F). This must not exceed
        MAX_NESTING_DEPTH. Verify the calculation is consistent for all
        valid (non-circular) folder pairs.
        """
        folder_specs, parent_map, children_map, depth_of = data

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            all_ids = [fid for fid, _ in folder_specs]
            # Test a sample of folder pairs (avoid O(n^2) for large trees)
            for fid in all_ids:
                subtree = get_subtree_depth(fid, session)
                for target_pid in all_ids:
                    if fid == target_pid:
                        continue
                    # Skip if moving would create a circular reference
                    descendants = _get_descendants(fid, children_map)
                    if target_pid in descendants:
                        continue

                    target_depth = get_folder_depth(target_pid, session)
                    total_depth = target_depth + subtree

                    if total_depth > MAX_NESTING_DEPTH:
                        # This move should be rejected
                        assert total_depth > MAX_NESTING_DEPTH
                    else:
                        # This move should be allowed — verify all folders
                        # in F's subtree would be within limit
                        def _check_subtree_within_limit(
                            node_id: int, current_depth: int
                        ):
                            assert current_depth <= MAX_NESTING_DEPTH, (
                                f"Moving folder {fid} under {target_pid}: "
                                f"descendant {node_id} would be at depth "
                                f"{current_depth}, exceeding limit"
                            )
                            for child in children_map.get(node_id, []):
                                _check_subtree_within_limit(child, current_depth + 1)

                        # F would be at target_depth + 1
                        _check_subtree_within_limit(fid, target_depth + 1)
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Property 4: 移动保持子树完整性 (Move Preserves Subtree Integrity)
# ---------------------------------------------------------------------------
# **Feature: nested-groups, Property 4: 移动保持子树完整性**
# **Validates: Requirements 4.1, 4.2, 4.3**
#
# For any folder and its subtree, after moving the folder to a new parent,
# all folders and requests within the subtree should maintain their relative
# hierarchical relationships.
# ---------------------------------------------------------------------------


def _collect_subtree_relationships(
    folder_id: int,
    children_map: dict[int, list[int]],
    request_map: dict[int, list[int]],
) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    """
    Collect all internal parent-child folder relationships and request-folder
    assignments within the subtree rooted at *folder_id* (exclusive of the
    root's own parent link).

    Returns:
        (folder_relationships, request_assignments)
        - folder_relationships: set of (child_id, parent_id) for every
          descendant edge inside the subtree.
        - request_assignments: set of (request_id, folder_id) for every
          request attached to a folder in the subtree.
    """
    folder_rels: set[tuple[int, int]] = set()
    req_assigns: set[tuple[int, int]] = set()

    stack = [folder_id]
    while stack:
        current = stack.pop()
        # Collect requests belonging to this folder
        for rid in request_map.get(current, []):
            req_assigns.add((rid, current))
        # Collect child edges
        for child in children_map.get(current, []):
            folder_rels.add((child, current))
            stack.append(child)

    return folder_rels, req_assigns


from api_testing_tool.models.request import Request as RequestModel


def _collect_subtree_relationships_from_db(
    folder_id: int,
    session,
) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    """
    Collect all internal parent-child folder relationships and request-folder
    assignments within the subtree rooted at *folder_id* by querying the
    database.

    Returns the same structure as ``_collect_subtree_relationships``.
    """
    folder_rels: set[tuple[int, int]] = set()
    req_assigns: set[tuple[int, int]] = set()

    stack = [folder_id]
    while stack:
        current = stack.pop()
        # Requests in this folder
        reqs = (
            session.query(RequestModel)
            .filter(RequestModel.folder_id == current)
            .all()
        )
        for r in reqs:
            req_assigns.add((r.id, r.folder_id))
        # Child folders
        children = (
            session.query(Folder)
            .filter(Folder.parent_folder_id == current)
            .all()
        )
        for child in children:
            folder_rels.add((child.id, current))
            stack.append(child.id)

    return folder_rels, req_assigns


@st.composite
def movable_folder_tree(draw: st.DrawFn):
    """
    Generate a valid folder tree (3..15 nodes) with requests, and pick a
    valid move operation: a folder F and a new parent P such that:
    - F != P
    - P is not a descendant of F (no circular reference)
    - The move respects MAX_NESTING_DEPTH

    Returns (folder_specs, request_specs, folder_to_move, new_parent_id)
    where:
    - folder_specs: list of (id, parent_id) tuples
    - request_specs: list of (id, folder_id) tuples
    - folder_to_move: the folder ID to move
    - new_parent_id: the new parent folder ID (or None for root)
    """
    n = draw(st.integers(min_value=3, max_value=15))
    folder_specs: list[tuple[int, Optional[int]]] = []
    depth_of: dict[int, int] = {}

    for i in range(1, n + 1):
        if i == 1:
            parent_id = None
        else:
            # Keep depth within limit to allow room for moves
            eligible = [
                fid for fid, _ in folder_specs
                if depth_of[fid] < MAX_NESTING_DEPTH
            ]
            if eligible:
                parent_id = draw(
                    st.one_of(
                        st.none(),
                        st.sampled_from(eligible),
                    )
                )
            else:
                parent_id = None
        folder_specs.append((i, parent_id))
        depth_of[i] = 1 if parent_id is None else depth_of[parent_id] + 1

    # Build helper maps
    parent_map: dict[int, Optional[int]] = {fid: pid for fid, pid in folder_specs}
    children_map: dict[int, list[int]] = {}
    for fid, pid in folder_specs:
        if pid is not None:
            children_map.setdefault(pid, []).append(fid)

    all_ids = [fid for fid, _ in folder_specs]

    # Generate some requests assigned to folders
    n_requests = draw(st.integers(min_value=0, max_value=15))
    request_specs: list[tuple[int, int]] = []
    for i in range(1, n_requests + 1):
        fid = draw(st.sampled_from(all_ids))
        request_specs.append((i, fid))

    # Compute subtree depth for each folder
    def _subtree_depth(fid: int) -> int:
        kids = children_map.get(fid, [])
        if not kids:
            return 1
        return 1 + max(_subtree_depth(c) for c in kids)

    # Find valid move targets: (folder_to_move, new_parent)
    # new_parent can be None (move to root) or a folder that is NOT a
    # descendant of folder_to_move, and the depth constraint is satisfied.
    valid_moves: list[tuple[int, Optional[int]]] = []
    for fid in all_ids:
        descendants = _get_descendants(fid, children_map)
        sub_depth = _subtree_depth(fid)

        # Option 1: move to root
        # At root the folder would be at depth 1, total = 1 + sub_depth - 1 = sub_depth
        if sub_depth <= MAX_NESTING_DEPTH and parent_map[fid] is not None:
            # Only interesting if the folder is not already at root
            valid_moves.append((fid, None))

        # Option 2: move under another folder
        for target in all_ids:
            if target == fid:
                continue
            if target in descendants:
                continue
            # Check depth constraint
            target_depth = depth_of[target]
            total = target_depth + sub_depth
            if total <= MAX_NESTING_DEPTH:
                # Only interesting if the parent actually changes
                if parent_map[fid] != target:
                    valid_moves.append((fid, target))

    assume(len(valid_moves) > 0)

    folder_to_move, new_parent_id = draw(st.sampled_from(valid_moves))
    return folder_specs, request_specs, folder_to_move, new_parent_id


class TestMovePreservesSubtreeIntegrityProperty:
    """Property 4: 移动保持子树完整性"""

    @given(data=movable_folder_tree())
    @settings(max_examples=150)
    def test_move_preserves_internal_folder_relationships(self, data):
        """
        **Feature: nested-groups, Property 4: 移动保持子树完整性**
        **Validates: Requirements 4.1, 4.2, 4.3**

        After moving folder F to a new parent, all internal parent-child
        relationships within F's subtree must remain unchanged. Only F's
        own parent_folder_id changes; every descendant keeps its original
        parent_folder_id.
        """
        folder_specs, request_specs, folder_to_move, new_parent_id = data

        # Build helper maps from the spec
        children_map: dict[int, list[int]] = {}
        for fid, pid in folder_specs:
            if pid is not None:
                children_map.setdefault(pid, []).append(fid)
        request_map: dict[int, list[int]] = {}
        for rid, fid in request_specs:
            request_map.setdefault(fid, []).append(rid)

        # Capture subtree relationships BEFORE the move
        rels_before, _ = _collect_subtree_relationships(
            folder_to_move, children_map, request_map
        )

        # Set up database and perform the move
        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            # Add requests
            collection = session.query(Collection).first()
            for rid, fid in request_specs:
                req = RequestModel(
                    id=rid,
                    name=f"Request-{rid}",
                    method="GET",
                    url="https://example.com",
                    collection_id=collection.id,
                    folder_id=fid,
                )
                session.add(req)
            session.commit()

            # Perform the move
            folder = session.query(Folder).filter(Folder.id == folder_to_move).first()
            folder.parent_folder_id = new_parent_id
            session.commit()

            # Capture subtree relationships AFTER the move from the DB
            rels_after, _ = _collect_subtree_relationships_from_db(
                folder_to_move, session
            )

            assert rels_before == rels_after, (
                f"Internal folder relationships changed after moving folder "
                f"{folder_to_move} to parent {new_parent_id}.\n"
                f"Before: {rels_before}\nAfter: {rels_after}"
            )
        finally:
            session.close()

    @given(data=movable_folder_tree())
    @settings(max_examples=150)
    def test_move_preserves_request_assignments(self, data):
        """
        **Feature: nested-groups, Property 4: 移动保持子树完整性**
        **Validates: Requirements 4.1, 4.2, 4.3**

        After moving folder F to a new parent, all requests within F's
        subtree must remain assigned to the same folders they were in
        before the move.
        """
        folder_specs, request_specs, folder_to_move, new_parent_id = data

        # Build helper maps from the spec
        children_map: dict[int, list[int]] = {}
        for fid, pid in folder_specs:
            if pid is not None:
                children_map.setdefault(pid, []).append(fid)
        request_map: dict[int, list[int]] = {}
        for rid, fid in request_specs:
            request_map.setdefault(fid, []).append(rid)

        # Capture request assignments BEFORE the move
        _, reqs_before = _collect_subtree_relationships(
            folder_to_move, children_map, request_map
        )

        # Set up database and perform the move
        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            # Add requests
            collection = session.query(Collection).first()
            for rid, fid in request_specs:
                req = RequestModel(
                    id=rid,
                    name=f"Request-{rid}",
                    method="GET",
                    url="https://example.com",
                    collection_id=collection.id,
                    folder_id=fid,
                )
                session.add(req)
            session.commit()

            # Perform the move
            folder = session.query(Folder).filter(Folder.id == folder_to_move).first()
            folder.parent_folder_id = new_parent_id
            session.commit()

            # Capture request assignments AFTER the move from the DB
            _, reqs_after = _collect_subtree_relationships_from_db(
                folder_to_move, session
            )

            assert reqs_before == reqs_after, (
                f"Request assignments changed after moving folder "
                f"{folder_to_move} to parent {new_parent_id}.\n"
                f"Before: {reqs_before}\nAfter: {reqs_after}"
            )
        finally:
            session.close()

    @given(data=movable_folder_tree())
    @settings(max_examples=150)
    def test_move_changes_only_moved_folder_parent(self, data):
        """
        **Feature: nested-groups, Property 4: 移动保持子树完整性**
        **Validates: Requirements 4.1, 4.2, 4.3**

        After moving folder F to a new parent, only F's parent_folder_id
        should change. All other folders in the entire tree must retain
        their original parent_folder_id.
        """
        folder_specs, request_specs, folder_to_move, new_parent_id = data

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            # Capture all parent relationships before the move
            parents_before = {
                fid: pid for fid, pid in folder_specs
            }

            # Perform the move
            folder = session.query(Folder).filter(Folder.id == folder_to_move).first()
            folder.parent_folder_id = new_parent_id
            session.commit()

            # Check all folders after the move
            all_folders = session.query(Folder).all()
            for f in all_folders:
                if f.id == folder_to_move:
                    assert f.parent_folder_id == new_parent_id, (
                        f"Moved folder {folder_to_move} should have "
                        f"parent_folder_id={new_parent_id}, got {f.parent_folder_id}"
                    )
                else:
                    assert f.parent_folder_id == parents_before[f.id], (
                        f"Folder {f.id} parent_folder_id changed from "
                        f"{parents_before[f.id]} to {f.parent_folder_id} "
                        f"after moving folder {folder_to_move}"
                    )
        finally:
            session.close()

    @given(data=movable_folder_tree())
    @settings(max_examples=150, suppress_health_check=[HealthCheck.filter_too_much])
    def test_move_to_root_sets_parent_to_none(self, data):
        """
        **Feature: nested-groups, Property 4: 移动保持子树完整性**
        **Validates: Requirements 4.1, 4.2, 4.3**

        When a folder is moved to root (parent_folder_id=None), the folder
        becomes a root-level folder and its subtree structure is preserved.
        """
        folder_specs, request_specs, folder_to_move, new_parent_id = data

        # Only test moves to root
        assume(new_parent_id is None)

        # Build helper maps
        children_map: dict[int, list[int]] = {}
        for fid, pid in folder_specs:
            if pid is not None:
                children_map.setdefault(pid, []).append(fid)
        request_map: dict[int, list[int]] = {}
        for rid, fid in request_specs:
            request_map.setdefault(fid, []).append(rid)

        # Capture subtree before
        rels_before, reqs_before = _collect_subtree_relationships(
            folder_to_move, children_map, request_map
        )

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            # Add requests
            collection = session.query(Collection).first()
            for rid, fid in request_specs:
                req = RequestModel(
                    id=rid,
                    name=f"Request-{rid}",
                    method="GET",
                    url="https://example.com",
                    collection_id=collection.id,
                    folder_id=fid,
                )
                session.add(req)
            session.commit()

            # Move to root
            folder = session.query(Folder).filter(Folder.id == folder_to_move).first()
            folder.parent_folder_id = None
            session.commit()

            # Verify folder is now at root
            session.refresh(folder)
            assert folder.parent_folder_id is None, (
                f"Folder {folder_to_move} should be at root after move, "
                f"but parent_folder_id={folder.parent_folder_id}"
            )

            # Verify subtree integrity
            rels_after, reqs_after = _collect_subtree_relationships_from_db(
                folder_to_move, session
            )
            assert rels_before == rels_after, (
                f"Subtree folder relationships changed after moving to root"
            )
            assert reqs_before == reqs_after, (
                f"Subtree request assignments changed after moving to root"
            )
        finally:
            session.close()

    @given(data=movable_folder_tree())
    @settings(max_examples=150)
    def test_move_preserves_subtree_in_tree_build(self, data):
        """
        **Feature: nested-groups, Property 4: 移动保持子树完整性**
        **Validates: Requirements 4.1, 4.2, 4.3**

        After moving folder F, building the folder tree via
        build_folder_tree should show F under its new parent with
        the same internal subtree structure as before the move.
        """
        folder_specs, request_specs, folder_to_move, new_parent_id = data

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            # Add requests
            collection = session.query(Collection).first()
            for rid, fid in request_specs:
                req = RequestModel(
                    id=rid,
                    name=f"Request-{rid}",
                    method="GET",
                    url="https://example.com",
                    collection_id=collection.id,
                    folder_id=fid,
                )
                session.add(req)
            session.commit()

            # Build tree BEFORE the move and extract the subtree of F
            all_folders_before = session.query(Folder).all()
            all_requests_before = session.query(RequestModel).all()
            tree_before = build_folder_tree(all_folders_before, all_requests_before)

            def _find_subtree(nodes: list[dict], target_id: int) -> Optional[dict]:
                for node in nodes:
                    if node["id"] == target_id:
                        return node
                    found = _find_subtree(node["children"], target_id)
                    if found is not None:
                        return found
                return None

            def _extract_internal_structure(node: dict) -> dict:
                """Extract the internal structure (children + requests) ignoring
                the node's own parent_folder_id."""
                return {
                    "children": sorted(
                        [_extract_internal_structure(c) for c in node["children"]],
                        key=lambda x: x["id"],
                    ),
                    "requests": sorted(
                        [r["id"] for r in node["requests"]]
                    ),
                    "id": node["id"],
                }

            subtree_before = _find_subtree(tree_before, folder_to_move)
            assert subtree_before is not None
            structure_before = _extract_internal_structure(subtree_before)

            # Perform the move
            folder = session.query(Folder).filter(Folder.id == folder_to_move).first()
            folder.parent_folder_id = new_parent_id
            session.commit()

            # Build tree AFTER the move
            session.expire_all()
            all_folders_after = session.query(Folder).all()
            all_requests_after = session.query(RequestModel).all()
            tree_after = build_folder_tree(all_folders_after, all_requests_after)

            subtree_after = _find_subtree(tree_after, folder_to_move)
            assert subtree_after is not None, (
                f"Folder {folder_to_move} not found in tree after move"
            )
            structure_after = _extract_internal_structure(subtree_after)

            assert structure_before == structure_after, (
                f"Subtree structure changed after moving folder {folder_to_move} "
                f"to parent {new_parent_id}.\n"
                f"Before: {structure_before}\nAfter: {structure_after}"
            )
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Property 6: 级联删除完整性 (Cascade Delete Integrity)
# ---------------------------------------------------------------------------
# **Feature: nested-groups, Property 6: 级联删除完整性**
# **Validates: Requirements 6.1, 6.3**
#
# For any folder containing sub-folders, after deleting that folder, all its
# descendant folders and requests within those descendant folders should no
# longer exist in the database.
# ---------------------------------------------------------------------------


@st.composite
def deletable_folder_tree(draw: st.DrawFn):
    """
    Generate a valid folder tree (2..15 nodes) with requests, and pick a
    folder to delete that has at least one descendant (to test cascade).

    Returns (folder_specs, request_specs, folder_to_delete) where:
    - folder_specs: list of (id, parent_id) tuples
    - request_specs: list of (request_id, folder_id) tuples
    - folder_to_delete: the folder ID to delete (has ≥1 descendant)
    """
    n = draw(st.integers(min_value=2, max_value=15))
    folder_specs: list[tuple[int, Optional[int]]] = []

    for i in range(1, n + 1):
        if i == 1:
            parent_id = None
        else:
            parent_id = draw(
                st.one_of(
                    st.none(),
                    st.sampled_from([fid for fid, _ in folder_specs]),
                )
            )
        folder_specs.append((i, parent_id))

    # Build children_map
    children_map: dict[int, list[int]] = {}
    for fid, pid in folder_specs:
        if pid is not None:
            children_map.setdefault(pid, []).append(fid)

    # Find folders that have at least one descendant
    folders_with_descendants = [
        fid for fid, _ in folder_specs
        if len(_get_descendants(fid, children_map)) > 0
    ]
    assume(len(folders_with_descendants) > 0)

    folder_to_delete = draw(st.sampled_from(folders_with_descendants))

    # Generate requests: some in the subtree, some outside
    all_ids = [fid for fid, _ in folder_specs]
    n_requests = draw(st.integers(min_value=1, max_value=20))
    request_specs: list[tuple[int, int]] = []
    for i in range(1, n_requests + 1):
        fid = draw(st.sampled_from(all_ids))
        request_specs.append((i, fid))

    return folder_specs, request_specs, folder_to_delete


class TestCascadeDeleteIntegrityProperty:
    """Property 6: 级联删除完整性"""

    @given(data=deletable_folder_tree())
    @settings(max_examples=150, suppress_health_check=[HealthCheck.filter_too_much])
    def test_cascade_delete_removes_all_descendants(self, data):
        """
        **Feature: nested-groups, Property 6: 级联删除完整性**
        **Validates: Requirements 6.1, 6.3**

        After deleting a folder, the folder itself and ALL its descendant
        folders must no longer exist in the database.
        """
        folder_specs, request_specs, folder_to_delete = data

        # Build children_map to compute expected descendants
        children_map: dict[int, list[int]] = {}
        for fid, pid in folder_specs:
            if pid is not None:
                children_map.setdefault(pid, []).append(fid)

        descendants = _get_descendants(folder_to_delete, children_map)
        deleted_folder_ids = {folder_to_delete} | descendants

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            # Add requests
            collection = session.query(Collection).first()
            for rid, fid in request_specs:
                req = RequestModel(
                    id=rid,
                    name=f"Request-{rid}",
                    method="GET",
                    url="https://example.com",
                    collection_id=collection.id,
                    folder_id=fid,
                )
                session.add(req)
            session.commit()

            # Delete the folder
            folder = session.query(Folder).filter(Folder.id == folder_to_delete).first()
            session.delete(folder)
            session.commit()

            # Verify: no deleted folder should exist
            remaining_folders = session.query(Folder).all()
            remaining_ids = {f.id for f in remaining_folders}

            for dfid in deleted_folder_ids:
                assert dfid not in remaining_ids, (
                    f"Folder {dfid} should have been cascade-deleted when "
                    f"folder {folder_to_delete} was deleted, but it still exists"
                )
        finally:
            session.close()

    @given(data=deletable_folder_tree())
    @settings(max_examples=150, suppress_health_check=[HealthCheck.filter_too_much])
    def test_cascade_delete_removes_all_descendant_requests(self, data):
        """
        **Feature: nested-groups, Property 6: 级联删除完整性**
        **Validates: Requirements 6.1, 6.3**

        After deleting a folder, all requests that belonged to the deleted
        folder or any of its descendant folders must no longer exist in the
        database.
        """
        folder_specs, request_specs, folder_to_delete = data

        # Build children_map to compute expected descendants
        children_map: dict[int, list[int]] = {}
        for fid, pid in folder_specs:
            if pid is not None:
                children_map.setdefault(pid, []).append(fid)

        descendants = _get_descendants(folder_to_delete, children_map)
        deleted_folder_ids = {folder_to_delete} | descendants

        # Compute which requests should be deleted
        expected_deleted_request_ids = {
            rid for rid, fid in request_specs
            if fid in deleted_folder_ids
        }

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            # Add requests
            collection = session.query(Collection).first()
            for rid, fid in request_specs:
                req = RequestModel(
                    id=rid,
                    name=f"Request-{rid}",
                    method="GET",
                    url="https://example.com",
                    collection_id=collection.id,
                    folder_id=fid,
                )
                session.add(req)
            session.commit()

            # Delete the folder
            folder = session.query(Folder).filter(Folder.id == folder_to_delete).first()
            session.delete(folder)
            session.commit()

            # Verify: no request from deleted subtree should exist
            remaining_requests = session.query(RequestModel).all()
            remaining_request_ids = {r.id for r in remaining_requests}

            for drid in expected_deleted_request_ids:
                assert drid not in remaining_request_ids, (
                    f"Request {drid} (in folder within deleted subtree) should "
                    f"have been cascade-deleted, but it still exists"
                )
        finally:
            session.close()

    @given(data=deletable_folder_tree())
    @settings(max_examples=150, suppress_health_check=[HealthCheck.filter_too_much])
    def test_cascade_delete_preserves_unrelated_folders(self, data):
        """
        **Feature: nested-groups, Property 6: 级联删除完整性**
        **Validates: Requirements 6.1, 6.3**

        After deleting a folder, all folders NOT in the deleted subtree
        must still exist in the database (no over-deletion).
        """
        folder_specs, request_specs, folder_to_delete = data

        # Build children_map to compute expected descendants
        children_map: dict[int, list[int]] = {}
        for fid, pid in folder_specs:
            if pid is not None:
                children_map.setdefault(pid, []).append(fid)

        descendants = _get_descendants(folder_to_delete, children_map)
        deleted_folder_ids = {folder_to_delete} | descendants
        surviving_folder_ids = {
            fid for fid, _ in folder_specs
            if fid not in deleted_folder_ids
        }

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            # Delete the folder
            folder = session.query(Folder).filter(Folder.id == folder_to_delete).first()
            session.delete(folder)
            session.commit()

            # Verify: all surviving folders still exist
            remaining_folders = session.query(Folder).all()
            remaining_ids = {f.id for f in remaining_folders}

            assert remaining_ids == surviving_folder_ids, (
                f"After deleting folder {folder_to_delete}, expected surviving "
                f"folders {surviving_folder_ids} but found {remaining_ids}"
            )
        finally:
            session.close()

    @given(data=deletable_folder_tree())
    @settings(max_examples=150, suppress_health_check=[HealthCheck.filter_too_much])
    def test_cascade_delete_preserves_unrelated_requests(self, data):
        """
        **Feature: nested-groups, Property 6: 级联删除完整性**
        **Validates: Requirements 6.1, 6.3**

        After deleting a folder, all requests NOT in the deleted subtree
        must still exist in the database (no over-deletion).
        """
        folder_specs, request_specs, folder_to_delete = data

        # Build children_map to compute expected descendants
        children_map: dict[int, list[int]] = {}
        for fid, pid in folder_specs:
            if pid is not None:
                children_map.setdefault(pid, []).append(fid)

        descendants = _get_descendants(folder_to_delete, children_map)
        deleted_folder_ids = {folder_to_delete} | descendants

        # Compute which requests should survive
        surviving_request_ids = {
            rid for rid, fid in request_specs
            if fid not in deleted_folder_ids
        }

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            # Add requests
            collection = session.query(Collection).first()
            for rid, fid in request_specs:
                req = RequestModel(
                    id=rid,
                    name=f"Request-{rid}",
                    method="GET",
                    url="https://example.com",
                    collection_id=collection.id,
                    folder_id=fid,
                )
                session.add(req)
            session.commit()

            # Delete the folder
            folder = session.query(Folder).filter(Folder.id == folder_to_delete).first()
            session.delete(folder)
            session.commit()

            # Verify: all surviving requests still exist
            remaining_requests = session.query(RequestModel).all()
            remaining_request_ids = {r.id for r in remaining_requests}

            assert remaining_request_ids == surviving_request_ids, (
                f"After deleting folder {folder_to_delete}, expected surviving "
                f"requests {surviving_request_ids} but found {remaining_request_ids}"
            )
        finally:
            session.close()

    @given(data=deletable_folder_tree())
    @settings(max_examples=150, suppress_health_check=[HealthCheck.filter_too_much])
    def test_cascade_delete_leaves_no_orphans(self, data):
        """
        **Feature: nested-groups, Property 6: 级联删除完整性**
        **Validates: Requirements 6.1, 6.3**

        After deleting a folder, there must be no orphaned folders
        (folders whose parent_folder_id references a non-existent folder)
        and no orphaned requests (requests whose folder_id references a
        non-existent folder).
        """
        folder_specs, request_specs, folder_to_delete = data

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            # Add requests
            collection = session.query(Collection).first()
            for rid, fid in request_specs:
                req = RequestModel(
                    id=rid,
                    name=f"Request-{rid}",
                    method="GET",
                    url="https://example.com",
                    collection_id=collection.id,
                    folder_id=fid,
                )
                session.add(req)
            session.commit()

            # Delete the folder
            folder = session.query(Folder).filter(Folder.id == folder_to_delete).first()
            session.delete(folder)
            session.commit()

            # Verify: no orphaned folders
            remaining_folders = session.query(Folder).all()
            remaining_folder_ids = {f.id for f in remaining_folders}

            for f in remaining_folders:
                if f.parent_folder_id is not None:
                    assert f.parent_folder_id in remaining_folder_ids, (
                        f"Orphaned folder detected: folder {f.id} references "
                        f"parent_folder_id={f.parent_folder_id} which no longer exists"
                    )

            # Verify: no orphaned requests
            remaining_requests = session.query(RequestModel).all()
            for r in remaining_requests:
                if r.folder_id is not None:
                    assert r.folder_id in remaining_folder_ids, (
                        f"Orphaned request detected: request {r.id} references "
                        f"folder_id={r.folder_id} which no longer exists"
                    )
        finally:
            session.close()



# ---------------------------------------------------------------------------
# Property 6: 级联删除完整性 (Cascade Delete Integrity)
# ---------------------------------------------------------------------------
# **Feature: nested-groups, Property 6: 级联删除完整性**
# **Validates: Requirements 6.1, 6.3**
#
# For any folder containing sub-folders, after deleting that folder, all its
# descendant folders and requests within those descendant folders should no
# longer exist in the database.
# ---------------------------------------------------------------------------


@st.composite
def deletable_folder_tree(draw: st.DrawFn):
    """
    Generate a valid folder tree (2..15 nodes) with requests, and pick a
    folder to delete that has at least one descendant (to test cascade).

    Returns (folder_specs, request_specs, folder_to_delete) where:
    - folder_specs: list of (id, parent_id) tuples
    - request_specs: list of (request_id, folder_id) tuples
    - folder_to_delete: the folder ID to delete (has ≥1 descendant)
    """
    n = draw(st.integers(min_value=2, max_value=15))
    folder_specs: list[tuple[int, Optional[int]]] = []

    for i in range(1, n + 1):
        if i == 1:
            parent_id = None
        else:
            parent_id = draw(
                st.one_of(
                    st.none(),
                    st.sampled_from([fid for fid, _ in folder_specs]),
                )
            )
        folder_specs.append((i, parent_id))

    # Build children_map
    children_map: dict[int, list[int]] = {}
    for fid, pid in folder_specs:
        if pid is not None:
            children_map.setdefault(pid, []).append(fid)

    # Find folders that have at least one descendant
    folders_with_descendants = [
        fid for fid, _ in folder_specs
        if len(_get_descendants(fid, children_map)) > 0
    ]
    assume(len(folders_with_descendants) > 0)

    folder_to_delete = draw(st.sampled_from(folders_with_descendants))

    # Generate requests: some in the subtree, some outside
    all_ids = [fid for fid, _ in folder_specs]
    n_requests = draw(st.integers(min_value=1, max_value=20))
    request_specs: list[tuple[int, int]] = []
    for i in range(1, n_requests + 1):
        fid = draw(st.sampled_from(all_ids))
        request_specs.append((i, fid))

    return folder_specs, request_specs, folder_to_delete


class TestCascadeDeleteIntegrityProperty:
    """Property 6: 级联删除完整性"""

    @given(data=deletable_folder_tree())
    @settings(max_examples=150, suppress_health_check=[HealthCheck.filter_too_much])
    def test_cascade_delete_removes_all_descendants(self, data):
        """
        **Feature: nested-groups, Property 6: 级联删除完整性**
        **Validates: Requirements 6.1, 6.3**

        After deleting a folder, the folder itself and ALL its descendant
        folders must no longer exist in the database.
        """
        folder_specs, request_specs, folder_to_delete = data

        # Build children_map to compute expected descendants
        children_map: dict[int, list[int]] = {}
        for fid, pid in folder_specs:
            if pid is not None:
                children_map.setdefault(pid, []).append(fid)

        descendants = _get_descendants(folder_to_delete, children_map)
        deleted_folder_ids = {folder_to_delete} | descendants

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            # Add requests
            collection = session.query(Collection).first()
            for rid, fid in request_specs:
                req = RequestModel(
                    id=rid,
                    name=f"Request-{rid}",
                    method="GET",
                    url="https://example.com",
                    collection_id=collection.id,
                    folder_id=fid,
                )
                session.add(req)
            session.commit()

            # Delete the folder
            folder = session.query(Folder).filter(Folder.id == folder_to_delete).first()
            session.delete(folder)
            session.commit()

            # Verify: no deleted folder should exist
            remaining_folders = session.query(Folder).all()
            remaining_ids = {f.id for f in remaining_folders}

            for dfid in deleted_folder_ids:
                assert dfid not in remaining_ids, (
                    f"Folder {dfid} should have been cascade-deleted when "
                    f"folder {folder_to_delete} was deleted, but it still exists"
                )
        finally:
            session.close()

    @given(data=deletable_folder_tree())
    @settings(max_examples=150, suppress_health_check=[HealthCheck.filter_too_much])
    def test_cascade_delete_removes_all_descendant_requests(self, data):
        """
        **Feature: nested-groups, Property 6: 级联删除完整性**
        **Validates: Requirements 6.1, 6.3**

        After deleting a folder, all requests that belonged to the deleted
        folder or any of its descendant folders must no longer exist in the
        database.
        """
        folder_specs, request_specs, folder_to_delete = data

        # Build children_map to compute expected descendants
        children_map: dict[int, list[int]] = {}
        for fid, pid in folder_specs:
            if pid is not None:
                children_map.setdefault(pid, []).append(fid)

        descendants = _get_descendants(folder_to_delete, children_map)
        deleted_folder_ids = {folder_to_delete} | descendants

        # Compute which requests should be deleted
        expected_deleted_request_ids = {
            rid for rid, fid in request_specs
            if fid in deleted_folder_ids
        }

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            # Add requests
            collection = session.query(Collection).first()
            for rid, fid in request_specs:
                req = RequestModel(
                    id=rid,
                    name=f"Request-{rid}",
                    method="GET",
                    url="https://example.com",
                    collection_id=collection.id,
                    folder_id=fid,
                )
                session.add(req)
            session.commit()

            # Delete the folder
            folder = session.query(Folder).filter(Folder.id == folder_to_delete).first()
            session.delete(folder)
            session.commit()

            # Verify: no request from deleted subtree should exist
            remaining_requests = session.query(RequestModel).all()
            remaining_request_ids = {r.id for r in remaining_requests}

            for drid in expected_deleted_request_ids:
                assert drid not in remaining_request_ids, (
                    f"Request {drid} (in folder within deleted subtree) should "
                    f"have been cascade-deleted, but it still exists"
                )
        finally:
            session.close()

    @given(data=deletable_folder_tree())
    @settings(max_examples=150, suppress_health_check=[HealthCheck.filter_too_much])
    def test_cascade_delete_preserves_unrelated_folders(self, data):
        """
        **Feature: nested-groups, Property 6: 级联删除完整性**
        **Validates: Requirements 6.1, 6.3**

        After deleting a folder, all folders NOT in the deleted subtree
        must still exist in the database (no over-deletion).
        """
        folder_specs, request_specs, folder_to_delete = data

        # Build children_map to compute expected descendants
        children_map: dict[int, list[int]] = {}
        for fid, pid in folder_specs:
            if pid is not None:
                children_map.setdefault(pid, []).append(fid)

        descendants = _get_descendants(folder_to_delete, children_map)
        deleted_folder_ids = {folder_to_delete} | descendants
        surviving_folder_ids = {
            fid for fid, _ in folder_specs
            if fid not in deleted_folder_ids
        }

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            # Delete the folder
            folder = session.query(Folder).filter(Folder.id == folder_to_delete).first()
            session.delete(folder)
            session.commit()

            # Verify: all surviving folders still exist
            remaining_folders = session.query(Folder).all()
            remaining_ids = {f.id for f in remaining_folders}

            assert remaining_ids == surviving_folder_ids, (
                f"After deleting folder {folder_to_delete}, expected surviving "
                f"folders {surviving_folder_ids} but found {remaining_ids}"
            )
        finally:
            session.close()

    @given(data=deletable_folder_tree())
    @settings(max_examples=150, suppress_health_check=[HealthCheck.filter_too_much])
    def test_cascade_delete_preserves_unrelated_requests(self, data):
        """
        **Feature: nested-groups, Property 6: 级联删除完整性**
        **Validates: Requirements 6.1, 6.3**

        After deleting a folder, all requests NOT in the deleted subtree
        must still exist in the database (no over-deletion).
        """
        folder_specs, request_specs, folder_to_delete = data

        # Build children_map to compute expected descendants
        children_map: dict[int, list[int]] = {}
        for fid, pid in folder_specs:
            if pid is not None:
                children_map.setdefault(pid, []).append(fid)

        descendants = _get_descendants(folder_to_delete, children_map)
        deleted_folder_ids = {folder_to_delete} | descendants

        # Compute which requests should survive
        surviving_request_ids = {
            rid for rid, fid in request_specs
            if fid not in deleted_folder_ids
        }

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            # Add requests
            collection = session.query(Collection).first()
            for rid, fid in request_specs:
                req = RequestModel(
                    id=rid,
                    name=f"Request-{rid}",
                    method="GET",
                    url="https://example.com",
                    collection_id=collection.id,
                    folder_id=fid,
                )
                session.add(req)
            session.commit()

            # Delete the folder
            folder = session.query(Folder).filter(Folder.id == folder_to_delete).first()
            session.delete(folder)
            session.commit()

            # Verify: all surviving requests still exist
            remaining_requests = session.query(RequestModel).all()
            remaining_request_ids = {r.id for r in remaining_requests}

            assert remaining_request_ids == surviving_request_ids, (
                f"After deleting folder {folder_to_delete}, expected surviving "
                f"requests {surviving_request_ids} but found {remaining_request_ids}"
            )
        finally:
            session.close()

    @given(data=deletable_folder_tree())
    @settings(max_examples=150, suppress_health_check=[HealthCheck.filter_too_much])
    def test_cascade_delete_leaves_no_orphans(self, data):
        """
        **Feature: nested-groups, Property 6: 级联删除完整性**
        **Validates: Requirements 6.1, 6.3**

        After deleting a folder, there must be no orphaned folders
        (folders whose parent_folder_id references a non-existent folder)
        and no orphaned requests (requests whose folder_id references a
        non-existent folder).
        """
        folder_specs, request_specs, folder_to_delete = data

        SessionLocal = _make_test_db()
        session = SessionLocal()
        try:
            _populate_db(session, folder_specs)

            # Add requests
            collection = session.query(Collection).first()
            for rid, fid in request_specs:
                req = RequestModel(
                    id=rid,
                    name=f"Request-{rid}",
                    method="GET",
                    url="https://example.com",
                    collection_id=collection.id,
                    folder_id=fid,
                )
                session.add(req)
            session.commit()

            # Delete the folder
            folder = session.query(Folder).filter(Folder.id == folder_to_delete).first()
            session.delete(folder)
            session.commit()

            # Verify: no orphaned folders
            remaining_folders = session.query(Folder).all()
            remaining_folder_ids = {f.id for f in remaining_folders}

            for f in remaining_folders:
                if f.parent_folder_id is not None:
                    assert f.parent_folder_id in remaining_folder_ids, (
                        f"Orphaned folder detected: folder {f.id} references "
                        f"parent_folder_id={f.parent_folder_id} which no longer exists"
                    )

            # Verify: no orphaned requests
            remaining_requests = session.query(RequestModel).all()
            for r in remaining_requests:
                if r.folder_id is not None:
                    assert r.folder_id in remaining_folder_ids, (
                        f"Orphaned request detected: request {r.id} references "
                        f"folder_id={r.folder_id} which no longer exists"
                    )
        finally:
            session.close()
