# Render a DOCX or PPTX to PDF with the installed Office application.
#
# Word and PowerPoint own the layout engine that produced these files, so they are
# what should render the PDF: a third-party converter reflows the document and the
# pagination stops matching what the author saw. Fields such as the page number in
# the running header are updated before export.
#
# Usage:
#   powershell -File evidence/to_pdf.ps1 -Source <file.docx|file.pptx> -Destination <file.pdf>
#
# The parameters are Source/Destination rather than Input/Output because $Input is a
# PowerShell automatic variable and cannot be bound as a parameter.

param(
    [Parameter(Mandatory = $true)][string]$Source,
    [Parameter(Mandatory = $true)][string]$Destination
)

$ErrorActionPreference = 'Stop'
$in = (Resolve-Path $Source).Path
$out = [System.IO.Path]::GetFullPath($Destination)
$ext = [System.IO.Path]::GetExtension($in).ToLower()

if ($ext -eq '.docx') {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    try {
        $doc = $word.Documents.Open($in, $false, $true)   # read-only
        # Repaginate and refresh the header field before measuring anything.
        $doc.Fields.Update() | Out-Null
        $doc.Repaginate()
        $pages = $doc.ComputeStatistics(2)                # wdStatisticPages
        $words = $doc.ComputeStatistics(0)                # wdStatisticWords
        $doc.ExportAsFixedFormat($out, 17)                # wdExportFormatPDF
        Write-Output "PDF written: $out"
        Write-Output "Pages: $pages   Words (whole document, Word's count): $words"
        $doc.Close($false)
    } finally {
        $word.Quit()
    }
}
elseif ($ext -eq '.pptx') {
    $ppt = New-Object -ComObject PowerPoint.Application
    try {
        $pres = $ppt.Presentations.Open($in, $true, $false, $false)
        # SaveCopyAs with ppSaveAsPDF (32). ExportAsFixedFormat takes a long
        # optional-argument list that PowerShell cannot bind positionally, and
        # SaveCopyAs leaves the open presentation bound to its original path.
        $pres.SaveCopyAs($out, 32)
        Write-Output "PDF written: $out"
        Write-Output "Slides: $($pres.Slides.Count)"
        $pres.Close()
    } finally {
        $ppt.Quit()
    }
}
else {
    throw "unsupported input: $ext"
}
