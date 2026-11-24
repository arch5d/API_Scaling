$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$pages = Get-Content -Raw (Join-Path $PSScriptRoot 'drawing.json') | ConvertFrom-Json
foreach ($page in $pages.PSObject.Properties) {
    $bitmap = New-Object System.Drawing.Bitmap 1600,900
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = 'AntiAlias'
    $graphics.TextRenderingHint = 'AntiAliasGridFit'
    foreach ($shape in $page.Value) {
        $color = [System.Drawing.ColorTranslator]::FromHtml($shape.color)
        $brush = New-Object System.Drawing.SolidBrush $color
        switch ($shape.kind) {
            'rect' { $graphics.FillRectangle($brush, [single]$shape.x, [single]$shape.y, [single]$shape.w, [single]$shape.h) }
            'text' {
                $font = New-Object System.Drawing.Font 'Arial',([single]$shape.size),([System.Drawing.FontStyle]::Regular),([System.Drawing.GraphicsUnit]::Pixel)
                $graphics.DrawString($shape.value, $font, $brush, [single]$shape.x, [single]$shape.y)
                $font.Dispose()
            }
            'line' {
                $pen = New-Object System.Drawing.Pen $color,4
                $graphics.DrawLine($pen, [single]$shape.x, [single]$shape.y, [single]$shape.xx, [single]$shape.yy)
                $pen.Dispose()
            }
        }
        $brush.Dispose()
    }
    $bitmap.Save((Join-Path $PSScriptRoot ($page.Name + '.png')), [System.Drawing.Imaging.ImageFormat]::Png)
    $graphics.Dispose()
    $bitmap.Dispose()
}
