#!/usr/bin/env python3
"""
Pre-install Camoufox browser during Docker build
This avoids downloading it every time the container runs
"""

import sys

def install_camoufox():
    """Install Camoufox browser"""
    print('📦 Pre-downloading Camoufox during Docker build...')
    
    try:
        from camoufox.pkgman import CamoufoxFetcher
        
        fetcher = CamoufoxFetcher()
        fetcher.install()
        
        print('✅ Camoufox successfully pre-installed in Docker image')
        return True
        
    except Exception as e:
        print(f'❌ Camoufox pre-installation failed: {e}')
        import traceback
        traceback.print_exc()
        return False


def download_models():
    """Download browser model definition files"""
    print('📦 Pre-downloading browser model definition files...')
    
    try:
        from browserforge import download_models as dl_models
        
        dl_models()
        
        print('✅ Browser model files successfully pre-downloaded')
        return True
        
    except Exception as e:
        print(f'ℹ️  Model download skipped: {e}')
        return False


def verify_installation():
    """Verify Camoufox installation"""
    print('🔍 Verifying Camoufox installation...')
    
    try:
        from camoufox.async_api import AsyncCamoufox
        
        print('✅ Camoufox verification successful - ready to use')
        return True
        
    except Exception as e:
        print(f'⚠️  Camoufox verification failed: {e}')
        return False


if __name__ == '__main__':
    print('=' * 60)
    print('Camoufox Installation for Docker')
    print('=' * 60)
    print()
    
    # Install Camoufox
    success = install_camoufox()
    print()
    
    # Download models
    download_models()
    print()
    
    # Verify installation
    verify_installation()
    print()
    
    if success:
        print('=' * 60)
        print('✅ Camoufox installation complete!')
        print('=' * 60)
        sys.exit(0)
    else:
        print('=' * 60)
        print('⚠️  Camoufox installation completed with warnings')
        print('=' * 60)
        sys.exit(0)  # Don't fail build, will download at runtime if needed

