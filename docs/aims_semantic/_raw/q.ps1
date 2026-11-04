param([Parameter(Mandatory)][string]$Database,[Parameter(Mandatory)][string]$Sql,[int]$Max=60)
# Read-only helper: SELECT/WITH only, READ UNCOMMITTED, 60s timeout, row cap.
if ($Sql -notmatch '^\s*(SELECT|WITH)\b' -or $Sql -match '(?i)\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|CREATE|TRUNCATE|EXEC|EXECUTE|INTO\s+[#\w])\b') { throw "Only plain SELECT queries are allowed." }
$cs="Driver={ODBC Driver 17 for SQL Server};Server=10.180.1.10;Database=$Database;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;ApplicationIntent=ReadOnly;Connection Timeout=15"
$c=New-Object System.Data.Odbc.OdbcConnection($cs); $c.Open()
$cmd=$c.CreateCommand(); $cmd.CommandTimeout=60; $cmd.CommandText="SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED; $Sql"
$da=New-Object System.Data.Odbc.OdbcDataAdapter($cmd); $dt=New-Object System.Data.DataTable; [void]$da.Fill($dt); $c.Close()
$dt | Select-Object -First $Max | Format-Table -AutoSize -Wrap | Out-String -Width 250
"(rows shown: $([Math]::Min($Max,$dt.Rows.Count)) of $($dt.Rows.Count))"


