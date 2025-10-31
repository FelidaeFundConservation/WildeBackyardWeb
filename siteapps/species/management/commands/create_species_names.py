from django.core.management.base import BaseCommand

from siteapps.species.models import SpeciesName


class Command(BaseCommand):
    help = "Creates objects for species names if they don't exist."

    def handle(self, *args, **options):
        species_names = [
            ("Acorn Woodpecker", "Melanerpes formicivorus"),
            ("American Badger", "Taxidea taxus"),
            ("American crow", "Corvus brachyrhynchos"),
            ("American Robin", "Turdus migratorius"),
            ("Black bear", "Ursus americanus"),
            ("Black-tailed jackrabbit", "Lepus californicus"),
            ("Bobcat", "Lynx rufus"),
            ("Brush rabbit", "Sylvilagus bachmani"),
            ("Burrowing Owl", "Athene cunicularia"),
            ("California Quail", "Callipepla californica"),
            ("California Thrasher", "Toxostoma redivivum"),
            ("California Towhee", "Melozone crissalis"),
            ("Canada Goose", "Branta canadensis"),
            ("Common raven", "Corvus corax"),
            ("Coyote", "Canis latrans"),
            ("Dark-eyed Junco", "Junco hyemalis"),
            ("Domestic cat", "Felis domesticus"),
            ("Domestic dog", "Canis lupus familiaris"),
            ("Domestic horse", "Equus caballus"),
            ("Eastern grey squirrel", "Sciurus carolinensis"),
            ("Golden Eagle", "Aquila chrysaetos"),
            ("Gray fox", "Urocyon cinereoargenteus"),
            ("Great horned owl", "Bubo virginianus"),
            ("House finch", "Haemorhous mexicanus"),
            ("Human", "Homo sapiens"),
            ("Long-tailed Weasel", "Mustela frenata"),
            ("Merriam's Chipmunk", "Neotamias merriami"),
            ("Mourning dove", "Zenaida macroura"),
            ("Mule deer", "Odocoileus hemionus"),
            ("Puma", "Puma concolor"),
            ("Raccoon", "Procyon lotor"),
            ("Red fox", "Vulpes vulpes"),
            ("Red-Shouldered Hawk", "Buteo lineatus"),
            ("Red-tailed hawk", "Buteo jamaicensis"),
            ("River otter", "Lontra canadensis"),
            ("Sheep (domestic)", "Ovis aries"),
            ("Spotted Skunk", "Spilogale gracilis"),
            ("Steller's Jay", "Cyanocitta stelleri"),
            ("Striped Skunk", "Mephitis mephitis"),
            ("Turkey", "Meleagris gallopavo"),
            ("Turkey Vulture", "Cathartes aura"),
            ("Virginia Opossum", "Didelphis viginiana"),
            ("Western Screech owl", "Megascops kennicottii"),
            ("Western scrub-jay", "Aphelocoma californica"),
            ("Wild Boar", "Sus scrofa"),
        ]

        for data in species_names:
            SpeciesName.objects.get_or_create(name=data[0], scientific_name=data[1])
