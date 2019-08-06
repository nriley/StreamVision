# -*- mode: python -*-

block_cipher = None


a = Analysis(['StreamVision.py'],
             pathex=['/Users/nicholas/Documents/Development/StreamVision'],
             binaries=[('build/lib.macosx-10.14-intel-2.7/AudioDevice.so', '.')],
             datas=[('AuthKey_8937YX2XGP.p8', '.')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='StreamVision',
          debug=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=True) # suppresses process transformation to foreground
app = BUNDLE(exe,
             name='StreamVision.app',
             info_plist=dict(
                 CFBundleIdentifier='net.sabi.StreamVision',
                 CFBundleName='StreamVision',
                 NSPrincipalClass='StreamVision',
                 LSUIElement=1,
             )
            )
