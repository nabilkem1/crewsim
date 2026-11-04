$ErrorActionPreference="Stop"
function Q($db,$sql){ $cs="Driver={ODBC Driver 17 for SQL Server};Server=10.180.1.10;Database=$db;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=15"
 $c=New-Object System.Data.Odbc.OdbcConnection($cs); $c.Open(); $cmd=$c.CreateCommand(); $cmd.CommandText=$sql; $cmd.CommandTimeout=120
 $da=New-Object System.Data.Odbc.OdbcDataAdapter($cmd); $dt=New-Object System.Data.DataTable; [void]$da.Fill($dt); $c.Close(); ,$dt }
$names = "CRROUTE,CRCODES,ROSTER,CREWLEG,CREWCAT,CREWQUAL,CRLEGGROUND,LEGTIMES,LEGMAIN,HOTAC,HOTEL,GENCAT,TABLES,SPEFRECDATA,SPEFREC2,SPEFREC3,EXPI,ROSTERID,CREWCATEG,COUNTRYCATEG,PORTCATEG,PORTCATEG2,CITYCATEG,ACCATEG,ACCATEG2,AIRCTYPE,vvFMSCodes,vvAirports,vvCREWDB,vvPositions,vvCarriers,vvZONEIDX,vvAIRCTYPE,vvFMSInfo1,vvallwrdc,VVCREXPREC,vvCountries".Split(",")
$in = ($names | % { "'$_'" }) -join ","
$cols = Q "TSC" "SELECT o.name obj, o.type_desc otype, c.column_id cid, c.name col, t.name typ, c.max_length len, c.precision prec, c.scale sc, c.is_nullable nul, c.is_identity idn, c.is_computed comp, ISNULL(ep.value,'') descr FROM sys.objects o JOIN sys.columns c ON c.object_id=o.object_id JOIN sys.types t ON t.user_type_id=c.user_type_id LEFT JOIN sys.extended_properties ep ON ep.major_id=o.object_id AND ep.minor_id=c.column_id AND ep.name='MS_Description' WHERE o.schema_id=1 AND o.name IN ($in) ORDER BY o.name,c.column_id"
$cols | Select-Object obj,otype,cid,col,typ,len,prec,sc,nul,idn,comp,descr | ConvertTo-Json -Compress | Set-Content _raw\columns.json -Encoding UTF8
$found = $cols | Group-Object obj | % Name
"found: " + ($found -join ",")
"missing: " + (($names | ? { $_ -notin $found }) -join ",")
$pk = Q "TSC" "SELECT o.name obj, i.name idx, i.is_primary_key pk, i.is_unique uq, STRING_AGG(c.name,',') WITHIN GROUP (ORDER BY ic.key_ordinal) cols FROM sys.objects o JOIN sys.indexes i ON i.object_id=o.object_id JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id AND ic.is_included_column=0 JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id WHERE o.schema_id=1 AND o.name IN ($in) AND o.type='U' GROUP BY o.name,i.name,i.is_primary_key,i.is_unique ORDER BY 1,3 DESC"
$pk | Select-Object obj,idx,pk,uq,cols | ConvertTo-Json -Compress | Set-Content _raw\indexes.json -Encoding UTF8
$fk = Q "TSC" "SELECT OBJECT_NAME(f.parent_object_id) child, OBJECT_NAME(f.referenced_object_id) parent, f.name fk FROM sys.foreign_keys f WHERE OBJECT_NAME(f.parent_object_id) IN ($in) OR OBJECT_NAME(f.referenced_object_id) IN ($in)"
"fks: " + $fk.Rows.Count
$rc = Q "TSC" "SELECT o.name obj, SUM(p.rows) n FROM sys.objects o JOIN sys.partitions p ON p.object_id=o.object_id AND p.index_id IN (0,1) WHERE o.schema_id=1 AND o.type='U' AND o.name IN ($in) GROUP BY o.name"
$rc | Select-Object obj,n | ConvertTo-Json -Compress | Set-Content _raw\rowcounts.json -Encoding UTF8
$v = Q "TSC" "SELECT o.name obj, m.definition def FROM sys.objects o JOIN sys.sql_modules m ON m.object_id=o.object_id WHERE o.schema_id=1 AND o.type='V' AND o.name IN ($in)"
$v | Select-Object obj,def | ConvertTo-Json -Compress | Set-Content _raw\view_defs.json -Encoding UTF8
"views: " + $v.Rows.Count
$cs = Q "CrewSchedAI" "SELECT o.name obj, c.column_id cid, c.name col, t.name typ, c.max_length len, c.precision prec, c.scale sc, c.is_nullable nul FROM sys.objects o JOIN sys.columns c ON c.object_id=o.object_id JOIN sys.types t ON t.user_type_id=c.user_type_id WHERE o.type='U' AND o.name IN ('crew_base_timezone','draft_order10_crews','FtcLegalLimit','position_category') ORDER BY o.name,c.column_id"
$cs | Select-Object obj,cid,col,typ,len,prec,sc,nul | ConvertTo-Json -Compress | Set-Content _raw\crewschedai_columns.json -Encoding UTF8
$crc = Q "CrewSchedAI" "SELECT o.name obj, SUM(p.rows) n FROM sys.objects o JOIN sys.partitions p ON p.object_id=o.object_id AND p.index_id IN (0,1) WHERE o.type='U' AND o.name IN ('crew_base_timezone','draft_order10_crews','FtcLegalLimit','position_category') GROUP BY o.name"
$crc | Select-Object obj,n | ConvertTo-Json -Compress | Set-Content _raw\crewschedai_rowcounts.json -Encoding UTF8
"done"
