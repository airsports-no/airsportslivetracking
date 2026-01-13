@echo off
@rem Davkovy subor urceny na vytvorenie startovnej listiny pre jednu konkretnu ulohu v AirSports
@rem na zaklade udajov z definicie trate v ANRWIN (zo subotu StartSequenceX.txt). 
@rem Spustenie:
@rem      _aktualizuj_sutaziacich.bat X Y
@rem kde X je cislo ulohy v ANRWIN (1..10), ktorej startova listina sa ma naimportovat do AirSports
@rem   a Y je ID ulohy v AirSports, do ktorej sa startova listina naimportuje

@rem DATA_DIR je uplna cesta do datoveho adresara sutaze v ANRWIN programe
@set DATA_DIR=D:\2024 WANR_Kamenica\7 Life tracking\LiveTracking_Airsports\WANR2024\

@rem CONTEST_ID je ciselny identifikator sutaze v AirSports.no do ktorej sa priradi nova uloha
@set CONTEST_ID=663

@rem PYTHON je uplna cesta k interpreterovi Python. Ak sa nachadza v ceste PATH tak staci "python.exe".
@set PYTHON="D:\2024 WANR_Kamenica\7 Life tracking\LiveTracking_Airsports\bin\Python3810\python.exe"

rem =========================

@rem PRG je uplna cesta k python skriptu na vytvorenie startovej listiny v AirSports, za beznych okolnosti netreba upravovat
@set PRG=%cd%\..\src\update-participants.py

if .%1. == .. goto error
if .%2. == .. goto error

cd logs
%PYTHON% "%PRG%" --contest-id=%CONTEST_ID% --task-id=%2 "%DATA_DIR%\StartSequence%1.txt"
goto ok

:error
echo Chyba povinny parameter: cislo ulohy

:ok
pause
