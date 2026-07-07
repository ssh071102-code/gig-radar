from abc import ABC, abstractmethod

from gig_radar.models import RawItem


class SourceAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self) -> list[RawItem]:
        """Fetch raw items. A single source's failure should raise; the pipeline isolates it."""
        raise NotImplementedError
