import sys
import winreg
from pathlib import Path
import ctypes

def register_associations():
    # Paths
    project_dir = Path(__file__).resolve().parent.parent
    run_script = project_dir / "run_simpleplayer.pyw"
    icon_path = project_dir / "simpleplayer" / "resources" / "icon.ico"
    
    # Check Python executable
    python_exe = Path(sys.executable)
    pythonw_exe = python_exe.parent / "pythonw.exe"
    if not pythonw_exe.exists():
        pythonw_exe = python_exe
        
    # Command string
    cmd_str = f'"{pythonw_exe}" "{run_script}" "%1"'
    
    print(f"Registering associations...")
    print(f"Command line: {cmd_str}")
    print(f"Icon: {icon_path}")
    
    # Define file extensions to associate
    sys.path.insert(0, str(project_dir))
    from simpleplayer.engines.registry import BackendRegistry
    registry = BackendRegistry()
    extensions = registry.supported_extensions(include_planned=False)
    
    # Register the file type class
    prog_id = "SimplePlayer.Assoc"
    
    # 1. Register ProgID class
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{prog_id}") as key:
        winreg.SetValue(key, "", winreg.REG_SZ, "Chiptune / Emulated Music File")
        
    # 2. Register Icon
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{prog_id}\DefaultIcon") as key:
        winreg.SetValue(key, "", winreg.REG_SZ, str(icon_path))
        
    # 3. Register Shell Command
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{prog_id}\shell\open\command") as key:
        winreg.SetValue(key, "", winreg.REG_SZ, cmd_str)
        
    # 4. Associate extensions
    for ext in extensions:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{ext}") as key:
            winreg.SetValue(key, "", winreg.REG_SZ, prog_id)
        print(f"Associated extension: {ext}")
            
    # Notify shell of association changes
    print("Notifying Windows Shell of changes...")
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None) # SHCNE_ASSOCCHANGED
    print("File association setup completed successfully!")

if __name__ == "__main__":
    register_associations()
