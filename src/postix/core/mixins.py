from typing import Dict


class Exportable:
    """Returns data for the settings export."""

    @property
    def data(self) -> Dict:
        return {
            field.name: getattr(self, field.name, None) for field in self._meta.fields
        }

    def loaddata(self, data: Dict):
        field_names = [field.name for field in self._meta.fields]
        for key, value in data.items():
            if key != "id" and key in field_names:
                setattr(self, key, value)
        self.save()
