' Startet start_server.bat ohne sichtbares Konsolenfenster.
' Wird von der Windows-Aufgabenplanung aufgerufen (siehe ANLEITUNG_WINDOWS.md).
Dim fso, scriptDir, shell
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set shell = CreateObject("WScript.Shell")
shell.Run """" & scriptDir & "\start_server.bat""", 0, False
