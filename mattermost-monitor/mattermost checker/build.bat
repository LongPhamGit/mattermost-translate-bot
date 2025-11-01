pyinstaller --clean --onefile --windowed ^
  --name "MattermostChecker" ^
  --icon=icon.ico ^
  --add-data "icon.ico;." ^
  --add-data "icon.png;." ^
  MattermostChecker.py
