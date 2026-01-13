@rem Spustenie tohto davkoveho suboru vyvola vytvorenie resp. aktualizaciu startovej
@rem listiny v AirSports podla zadania v StartSequence1.txt

@rem Pred prvym pouzitim treba nastavit:
@rem   prvy parameter: cislo ulohy z ANRWIN 
@rem   druhy parameter: ID ulohy v AirSports, do ktorej sa startova listina naimportuje

call _aktualizuj_sutaziacich.bat X 0000
