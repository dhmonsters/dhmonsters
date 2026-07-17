# Microsoft Word를 숨김 상태로 사용해 Planet Solver 보고서를 읽기 전용 PDF로 변환
param(
    [Parameter(Mandatory = $true)]
    [string]$InputDocx,
    [Parameter(Mandatory = $true)]
    [string]$OutputPdf
)

$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($InputDocx, $false, $true)
    $doc.ExportAsFixedFormat($OutputPdf, 17)
}
finally {
    if ($null -ne $doc) {
        $doc.Close([ref]$false)
    }
    if ($null -ne $word) {
        $word.Quit()
    }
}
