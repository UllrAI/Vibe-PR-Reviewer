

from utils.diff_parser import parse_diff

def test_parse_diff_single_file_addition():
    diff = """
diff --git a/new_file.py b/new_file.py
new file mode 100644
index 0000000..a1b2c3d
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,3 @@
+def hello():
+    print("Hello, world!")
+
"""
    parsed = parse_diff(diff)
    assert len(parsed) == 1
    assert parsed[0]["file_path"] == "new_file.py"
    assert "def hello()" in parsed[0]["diff"]
    assert len(parsed[0]["hunks"]) == 1
    assert parsed[0]["hunks"][0]["target_start_line"] == 1

def test_parse_diff_single_file_modification():
    diff = """
diff --git a/modified_file.txt b/modified_file.txt
index e69de29..8d0b62b 100644
--- a/modified_file.txt
+++ b/modified_file.txt
@@ -1,2 +1,3 @@
 line 1
-line 2
+line 2 modified
+line 3 added
"""
    parsed = parse_diff(diff)
    assert len(parsed) == 1
    assert parsed[0]["file_path"] == "modified_file.txt"
    assert "-line 2" in parsed[0]["diff"]
    assert "+line 2 modified" in parsed[0]["diff"]
    assert len(parsed[0]["hunks"]) == 1
    assert parsed[0]["hunks"][0]["target_start_line"] == 1

def test_parse_diff_multiple_files():
    diff = """
diff --git a/file1.py b/file1.py
index abcdef1..1234567 100644
--- a/file1.py
+++ b/file1.py
@@ -1,1 +1,2 @@
 print("old")
+print("new")
diff --git a/file2.js b/file2.js
index fedcba9..9876543 100644
--- a/file2.js
+++ b/file2.js
@@ -1,1 +1,1 @@
-console.log("old");
+console.log("new");
"""
    parsed = parse_diff(diff)
    assert len(parsed) == 2
    assert parsed[0]["file_path"] == "file1.py"
    assert parsed[1]["file_path"] == "file2.js"

def test_parse_diff_deletion():
    diff = """
diff --git a/deleted_file.txt b/deleted_file.txt
deleted file mode 100644
index 8d0b62b..0000000
--- a/deleted_file.txt
+++ /dev/null
@@ -1,3 +0,0 @@
-line 1
-line 2
-line 3
"""
    parsed = parse_diff(diff)
    assert len(parsed) == 1
    assert parsed[0]["file_path"] == "deleted_file.txt"
    assert "-line 1" in parsed[0]["diff"]

def test_parse_diff_empty():
    assert parse_diff("") == []

def test_parse_diff_no_changes():
    diff = """
diff --git a/no_change.txt b/no_change.txt
index e69de29..e69de29 100644
--- a/no_change.txt
+++ b/no_change.txt
"""
    parsed = parse_diff(diff)
    assert len(parsed) == 1
    assert parsed[0]["file_path"] == "no_change.txt"
    assert parsed[0]["diff"] == ""
    assert parsed[0]["hunks"] == []
