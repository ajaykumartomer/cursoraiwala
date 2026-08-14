@if (@X)==(@Y) @end /* hybrid: batch header, JScript body below
@echo off
setlocal
cd /d "%~dp0"

if not exist "MergedScripts.txt" (
    echo [ERROR] MergedScripts.txt not found in this folder.
    pause
    exit /b 1
)

echo.
echo ============================================
echo       DISINTEGRATING SCRIPTS
echo ============================================
echo.
echo Reading MergedScripts.txt
echo Writing .bat files into extracted_bats\
echo MergedScripts.txt will NOT be deleted.
echo.

cscript //nologo //e:jscript "%~f0"
echo.
pause
exit /b

*/

var fso = new ActiveXObject("Scripting.FileSystemObject");
var here = fso.GetParentFolderName(WScript.ScriptFullName);
var inPath = fso.BuildPath(here, "MergedScripts.txt");
var outDir = fso.BuildPath(here, "extracted_bats");

if (!fso.FileExists(inPath)) {
    WScript.Echo("[ERROR] MergedScripts.txt not found in this folder.");
    WScript.Quit(1);
}
if (!fso.FolderExists(outDir)) fso.CreateFolder(outDir);

function isBlank(s) {
    return String(s).replace(/\s/g, "") === "";
}

function saveFile(name, lines) {
    while (lines.length && isBlank(lines[lines.length - 1])) lines.pop();
    var base = String(name).replace(/\\/g, "/");
    var slash = base.lastIndexOf("/");
    if (slash >= 0) base = base.substring(slash + 1);
    if (!/\.bat$/i.test(base)) return false;
    if (/^mergedscripts\.txt$/i.test(base)) return false;
    var ts = fso.CreateTextFile(fso.BuildPath(outDir, base), true);
    for (var i = 0; i < lines.length; i++) ts.WriteLine(lines[i]);
    ts.Close();
    WScript.Echo("[+] " + base);
    return true;
}

var ts = fso.OpenTextFile(inPath, 1);
var headerRe = /^Script\s+\d+\s+\{(.+)\}\s*$/;
var current = null;
var buf = [];
var skip = 0;
var count = 0;

while (!ts.AtEndOfStream) {
    var line = ts.ReadLine();
    var m = line.match(headerRe);
    if (m) {
        if (current && saveFile(current, buf)) count++;
        current = m[1];
        buf = [];
        skip = 3;
        continue;
    }
    if (!current) continue;
    if (skip > 0) {
        if (isBlank(line)) { skip--; continue; }
        skip = 0;
    }
    buf.push(line);
}
ts.Close();
if (current && saveFile(current, buf)) count++;

WScript.Echo("");
WScript.Echo("Total Scripts Extracted: " + count);
WScript.Echo("MergedScripts.txt left untouched.");
if (count === 0) WScript.Quit(1);
