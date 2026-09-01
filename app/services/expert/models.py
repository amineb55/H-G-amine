"""Structured models for the expert's content files.

Every model refuses unknown fields: a typo in a record fails loudly with the
record named, never silently. Field names mirror the YAML files — they are
the expert's vocabulary, and the files are the source of truth.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

REQUIREMENT_TYPES = ("documentaire", "mise_en_oeuvre", "enregistrement")
DOCUMENT_FAMILIES = (
    "politique", "processus", "procedure", "instruction", "plan", "programme",
    "registre", "enregistrement", "rapport", "liste", "externe",
)
GLOSSARY_DOMAINS = (
    "hls", "sst", "qualite", "environnement", "energie", "audit", "outils",
    "sante", "maroc",
)


class ExpertRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _oui_non(value: object) -> bool:
    if value in ("oui", True):
        return True
    if value in ("non", False):
        return False
    raise ValueError(f"expected 'oui' or 'non', got {value!r}")


# --- requirements model (spec §3.4) ----------------------------------------


class Exigence(ExpertRecord):
    """One paraphrased requirement — never the standard's own text (P6)."""

    id: str = Field(pattern=r"^(45001|9001|14001|50001)-\d+(\.\d+)*[a-z]?$")
    chapitre: int = Field(ge=4, le=10)
    titre_fr: str = Field(min_length=1)
    titre_en: str
    exigence_fr: str = Field(min_length=1)
    # Empty until the reviewer translates; never machine-filled as final.
    exigence_en: str
    type: str
    preuves_attendues: list[str] = Field(min_length=1)
    questions_audit: list[str] = Field(min_length=1)
    documents_types: list[str]
    hls_commun: bool
    equivalences: list[str]
    applicabilite: str | list[str]
    regles_terrain: list[str]
    erreurs_frequentes: str
    poids: int = Field(ge=1, le=3)
    # A norm-specific record refining a common-core record it points to.
    nuance_de: str | None = None

    @field_validator("type")
    @classmethod
    def _known_type(cls, value: str) -> str:
        if value not in REQUIREMENT_TYPES:
            raise ValueError(f"unknown type {value!r}; expected one of {REQUIREMENT_TYPES}")
        return value

    @field_validator("hls_commun", mode="before")
    @classmethod
    def _bool_from_oui_non(cls, value: object) -> bool:
        return _oui_non(value)


class DocumentType(ExpertRecord):
    """One entry of the master list of document slugs."""

    libelle: str = Field(min_length=1)
    famille: str

    @field_validator("famille")
    @classmethod
    def _known_family(cls, value: str) -> str:
        if value not in DOCUMENT_FAMILIES:
            raise ValueError(f"unknown family {value!r}; expected one of {DOCUMENT_FAMILIES}")
        return value


# --- sector rule sets (Service 3) ------------------------------------------


class RegleTerrain(ExpertRecord):
    """One inspection rule, with what the engine looks for and what it spares."""

    id: str = Field(pattern=r"^[A-Z]{2,4}-\d{2}$")
    titre: str = Field(min_length=1)
    categorie: str = Field(min_length=1)
    description: str = Field(min_length=1)
    criticite_defaut: int = Field(ge=1, le=4)
    exigences: list[str] = Field(min_length=1)
    reference_reglementaire: str
    indices_visuels: list[str] = Field(min_length=1)
    exclusions: list[str]
    action_immediate: str


class FichierReglesTerrain(ExpertRecord):
    secteur: str = Field(min_length=1)
    version: str = Field(min_length=1)
    regles: list[RegleTerrain] = Field(min_length=1)


# --- framing form (Service 1, spec §4.1.1) ----------------------------------


class QuestionCadrage(ExpertRecord):
    id: str = Field(pattern=r"^Q\d+[a-z]?$")
    section: int = Field(ge=1, le=8)
    secteur: str = Field(min_length=1)
    norme: str = Field(min_length=1)
    seuil_minimal: bool
    type_reponse: str = Field(min_length=1)
    question: str = Field(min_length=1)
    documents: list[str]
    exigences: list[str]
    pourquoi: str = Field(min_length=1)

    @field_validator("norme", mode="before")
    @classmethod
    def _norm_as_text(cls, value: object) -> str:
        return str(value)

    @field_validator("seuil_minimal", mode="before")
    @classmethod
    def _bool_from_oui_non(cls, value: object) -> bool:
        return _oui_non(value)


class FormulaireCadrage(ExpertRecord):
    version: str = Field(min_length=1)
    sections: dict[int, str]
    seuil_minimal_regle: str = Field(min_length=1)
    questions: list[QuestionCadrage] = Field(min_length=1)


# --- glossary (P10 groundwork) ----------------------------------------------


class TermeGlossaire(ExpertRecord):
    fr: str = Field(min_length=1)
    en: str = Field(min_length=1)
    dom: str
    def_: str = Field(min_length=1, alias="def")

    @field_validator("dom")
    @classmethod
    def _known_domain(cls, value: str) -> str:
        if value not in GLOSSARY_DOMAINS:
            raise ValueError(f"unknown domain {value!r}; expected one of {GLOSSARY_DOMAINS}")
        return value


class Glossaire(ExpertRecord):
    version: str = Field(min_length=1)
    termes: list[TermeGlossaire] = Field(min_length=1)


# --- scales and grids (Services 2 and 3) ------------------------------------


class NiveauCriticite(ExpertRecord):
    niveau: int = Field(ge=1, le=4)
    libelle_fr: str
    libelle_en: str
    definition_fr: str
    delai_traitement_jours: int = Field(ge=0)
    consigne_fr: str
    delai_verification_jours: int = Field(ge=0)
    notification: list[str] = Field(min_length=1)
    notification_delai: str


class EscaladeCriticite(ExpertRecord):
    code: str = Field(pattern=r"^ESC-\d{2}$")
    condition_fr: str = Field(min_length=1)
    effet: str = Field(min_length=1)


class CriticiteConstats(ExpertRecord):
    niveaux: list[NiveauCriticite] = Field(min_length=4, max_length=4)
    escalade: list[EscaladeCriticite] = Field(min_length=1)
    plafond: int = Field(ge=1, le=4)
    regles_particulieres: list[str]


class NiveauEchelle(ExpertRecord):
    niveau: int = Field(ge=1, le=4)
    libelle_fr: str
    definition_fr: str


class CoefficientMaitrise(ExpertRecord):
    coefficient: float = Field(gt=0.0, le=1.0)
    libelle_fr: str


class SeuilRisque(ExpertRecord):
    plage: str
    classe: str
    action_fr: str


class CotationRisques(ExpertRecord):
    methode: str
    gravite: list[NiveauEchelle] = Field(min_length=1)
    probabilite_note_fr: str
    probabilite: list[NiveauEchelle] = Field(min_length=1)
    maitrise_note_fr: str
    maitrise: list[CoefficientMaitrise] = Field(min_length=1)
    criticite_brute: str
    criticite_residuelle: str
    seuils: list[SeuilRisque] = Field(min_length=1)
    regle_fr: str


class ClassificationNC(ExpertRecord):
    code: str
    libelle_fr: str
    libelle_en: str
    criteres_fr: list[str] = Field(min_length=1)
    consequence_fr: str


class DegreCouverture(ExpertRecord):
    valeur: int = Field(ge=0, le=100)
    libelle_fr: str
    definition_fr: str


class SeuilMaturite(ExpertRecord):
    plage: str
    libelle_fr: str
    message_fr: str


class CouvertureDocumentaire(ExpertRecord):
    degres: list[DegreCouverture] = Field(min_length=4, max_length=4)
    calcul: dict[str, str]
    seuils_maturite: list[SeuilMaturite] = Field(min_length=1)
    regles_bloquantes: list[str]


class PoidsExigence(ExpertRecord):
    poids: int = Field(ge=1, le=3)
    libelle_fr: str
    definition_fr: str


class Baremes(ExpertRecord):
    version: str = Field(min_length=1)
    criticite_constats: CriticiteConstats
    cotation_risques: CotationRisques
    classification_nc_audit: list[ClassificationNC] = Field(min_length=1)
    classification_nc_regle_de_remontee_fr: str
    couverture_documentaire: CouvertureDocumentaire
    ponderation: list[PoidsExigence] = Field(min_length=3, max_length=3)
    delais_declaration_maroc: dict[str, int | str]


# --- quality-tool decision tree (spec §4.3.3) -------------------------------


class QuestionQualification(ExpertRecord):
    id: str
    question_fr: str = Field(min_length=1)
    reponses: list[str] = Field(min_length=2)


class BrancheOutil(ExpertRecord):
    code: str
    situation_fr: str = Field(min_length=1)
    conditions: dict[str, str]
    outil: str = Field(min_length=1)
    livrable: str = Field(min_length=1)
    agent_preremplit: list[str] = Field(min_length=1)
    humain_complete: list[str] = Field(min_length=1)


class ArbreDecision(ExpertRecord):
    version: str = Field(min_length=1)
    questions_qualification: list[QuestionQualification] = Field(min_length=1)
    branches: list[BrancheOutil] = Field(min_length=1)
    regles_transversales: list[str]


# --- copyright guard patterns (P6) ------------------------------------------


class GuardPatterns(ExpertRecord):
    """The expert-maintained list of standard-like phrasings to refuse."""

    version: str = Field(min_length=1)
    interdits_fr: list[str] = Field(min_length=1)
    interdits_en: list[str] = Field(min_length=1)
    a_eviter_fr: list[str]
    a_eviter_en: list[str]
