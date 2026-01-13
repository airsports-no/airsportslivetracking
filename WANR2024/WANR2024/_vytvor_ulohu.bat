@echo off
@rem Davkovy subor urceny na vytvorenie trate a nasledne aj sutaznej ulohy v AirSports
@rem na zaklade udajov z definicie trate v ANRWIN (zo subotu GPSA_OUTx.TXT). 
@rem Spustenie:
@rem      _vytvor_ulohu.bat X
@rem kde X je cislo ulohy v ANRWIN (1..10), ktora sa ma naimportovat do AirSports.

@rem DATA_DIR je uplna cesta do datoveho adresara sutaze v ANRWIN programe
@set DATA_DIR=D:\2024 WANR_Kamenica\7 Life tracking\LiveTracking_Airsports\WANR2024TEST\

@rem CONTEST_ID je ciselny identifikator sutaze v AirSports.no do ktorej sa priradi nova uloha
@set CONTEST_ID=663

@rem TASK_BASENAME je zaklad nazvu pouzity pre vytvorenu ulohu, doplni sa o medzeru a cislo ulohy
set TASK_BASENAME=WANR 2024 Task

@rem PYTHON je uplna cesta k interpreterovi Python. Ak sa nachadza v ceste PATH tak staci "python.exe".
@set PYTHON="D:\2024 WANR_Kamenica\7 Life tracking\LiveTracking_Airsports\bin\Python3810\python.exe"

@rem =========================

@rem PRG je uplna cesta k python skriptu na vytvorenie ulohy v AirSports, za beznych okolnosti netreba upravovat
@set PRG=%cd%\..\src\create-task.py

if .%1. == .. goto error

cd logs
%PYTHON% "%PRG%" --name="%TASK_BASENAME% %1" --contest-id=%CONTEST_ID% "%DATA_DIR%\GPSA_OUT%1.TXT"
goto ok

:error
echo Chyba povinny parameter: cislo ulohy v ANRWIN programe

:ok
pause
