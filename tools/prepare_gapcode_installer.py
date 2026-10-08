"""Add resolved-path guards to the downloaded official Windows installer."""
from pathlib import Path

path=Path.home()/'.flux/integrations/gapcode-install.ps1'
text=path.read_text(encoding='utf-8-sig')
old='        Move-Item -LiteralPath $packageRoot -Destination $releaseDirectory'
new='''        $checkedSource = [IO.Path]::GetFullPath($packageRoot)
        $checkedDestination = [IO.Path]::GetFullPath($releaseDirectory)
        $allowedSourceRoot = [IO.Path]::GetFullPath($extractDirectory).TrimEnd('\\') + '\\'
        $allowedDestinationRoot = [IO.Path]::GetFullPath($releasesDirectory).TrimEnd('\\') + '\\'
        if (-not ($checkedSource + '\\').StartsWith($allowedSourceRoot, [StringComparison]::OrdinalIgnoreCase) -or
            -not $checkedDestination.StartsWith($allowedDestinationRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Resolved installation move escaped its intended roots.'
        }
        Move-Item -LiteralPath $checkedSource -Destination $checkedDestination'''
if old not in text:raise ValueError('Installer move changed; review again.')
text=text.replace(old,new)
old='        Remove-Item -LiteralPath $TemporaryRoot -Recurse -Force -ErrorAction SilentlyContinue'
new='''        $checkedTemporaryRoot = [IO.Path]::GetFullPath($TemporaryRoot)
        $allowedTemporaryPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\\') + '\\gapcode-install-'
        if (-not $checkedTemporaryRoot.StartsWith($allowedTemporaryPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Resolved cleanup path escaped its intended temporary root.'
        }
        Remove-Item -LiteralPath $checkedTemporaryRoot -Recurse -Force -ErrorAction SilentlyContinue'''
if old not in text:raise ValueError('Installer cleanup changed; review again.')
text=text.replace(old,new)
destination=path.with_name('gapcode-install-guarded.ps1')
destination.write_text(text,encoding='utf-8-sig')
print(destination)
