from django.apps import AppConfig
import jdatetime

class CoreConfig(AppConfig):
    name = 'core'
    
    def ready(self):
        try:
            jdatetime.set_locale('fa_IR')
        except Exception:
            pass
