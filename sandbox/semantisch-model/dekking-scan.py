#!/usr/bin/env python3
"""Dekkingsscan: hoeveel van de concepten die echt in de solutions voorkomen,
dekt het semantisch model (semantisch-model.schema.json)?

Scant alle solutions/**/*.mps, telt het gebruik van concepten per taal, en
verdeelt ze over drie emmers: GEDEKT (in het schema), BUITEN SCOPE / GENORMALISEERD
(bewust niet als eigen construct), en NOG TE DOEN (semantisch, komt voor, nog niet
gemodelleerd). Puur leesbaar; wijzigt niets.

Gebruik:  python3 sandbox/semantisch-model/dekking-scan.py [pad-naar-repo-root]
"""
import xml.etree.ElementTree as ET
import glob, sys, os, collections

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
LANGS = {"regelspraak", "gegevensspraak", "beslistabelspraak",
         "regelspraak.tijd", "gegevensspraak.tijd", "testspraak", "testspraak.tijd"}

# Concepten die het schema semantisch representeert (kortnaam, taal-agnostisch).
GEDEKT = {
    # gegevensspraak — objectschema, types, eenheden, dimensies, parameters
    "ObjectModel","ObjectType","ObjectExtensie","Attribuut","Kenmerk","Rol","FeitType",
    "Domein","DataType","NumeriekType","PercentageType","TekstType","BooleanType","DatumTijdType",
    "EnumeratieType","EnumeratieWaarde","DomeinType","GedimensioneerdType",
    "Dimensie","DimensieRef","DimensieFilter","Label","LabelRef","LabelFilterAlles",
    "LabelFilterInterval","LabelFilterVerzameling","Eenheid","EenheidMacht","EenheidSysteem",
    "BasisEenheid","Omrekenfactor","EenheidConversie","Parameter","Parameterset","Parametertoekenning",
    "Concatenatie","NumeriekeLiteral","PercentageLiteral","TekstLiteral","BooleanLiteral",
    "DatumTijdLiteral","EnumWaardeRef","Rekendatum","Rekenjaar","Expressie","Waarde","Literal",
    "Geldigheidsperiode","Dagsoort",
    # regelspraak — regels, acties, condities, navigatie, expressies
    "Regelgroep","Regel","RegelVersie","AbstracteRegel","ActieIndienVoorwaarde","Statement",
    "Variabele","VariabeleRef","ParameterRef","Gelijkstelling","Initialisatie","KenmerkToekenning",
    "ObjectCreatie","EigenschapInitialisatie","FeitCreatie","ConsistentieRegel","Verdeling",
    "Ontvanger","Afronding","DagsoortDefinitie","Conditie","EnkeleVoorwaarde","SamengesteldeVoorwaarde",
    "SamengesteldPredicaat","Subconditie","Uniciteit","Quantificatie","Alle","Geen","AantalQuantificatie",
    "Predicaat","Vergelijking","IsGevuld","IsLeeg","RolOfKenmerkCheck","IsDagsoort","ElfproefCheck",
    "IsNumeriekMetLengte","IsInconsistent","IsAfgevuurd","Selectie","Selector","AttribuutSelector",
    "DimAttribuutSelector","RolSelector","Combinatie","OnderwerpExpressie","OnderwerpRef","UnivOnderwerp",
    "AlleOnderwerp","SubSelectie","Aggregatie","DimensieAggregatie","ArithmetischeExpressie",
    "PlusExpressie","MinusExpressie","VermenigvuldigExpressie","DelenExpressie","Machtsverheffen",
    "Haakjes","Afronden","BegrensdeExpressie","GrensWaarde","PercentageVanExpressie","VerminderdMet",
    "Worteltrekken","AbsoluteWaarde","TekstExpressie","TekstDeel","Leeg","NumeriekeWaarde","DeDag",
    "DatumTijdVerschil","DatumElementUit","DatumMetJaarMaandEnDag","DatumMetJaarMaandDagEnTijd",
    "EerstePaasdag","DatumMetJaarEnVerstekwaardenVoorMaandEnDag","RegelgroepBundel","RegelsetRef",
    "RegelgroepConditie","RegelgroepConditieVersie","UnivVarRef","Term","TermList",
    # regelspraak.tijd
    "Periode","MultiPeriode","Totaal","TijdsduurDat","Tijdsevenredig","ConditioneleExpressie",
    "StartpuntBepaling","HeleTijdvak","ActieGedurendeDeTijdDatVoorwaarde",
    # gegevensspraak.tijd
    "Tijdlijn","Tijdgranulariteit","TijdlijnDefinitie","TijdlijnRef","Startpunt","Tijdsdimensie",
    "LiteralMetPeriode","TijdsafhankelijkeLiteral",
    # testspraak — datazijde
    "TestSet","TestGeval","Instantie","InstantieInitialisatie","EigenschapToekenning",
    "UitvoerVoorspelling","ConsistentieVoorspelling","TeTestenRegel","TeTestenRegelgroep",
    "TeTestenRegelset","Resultaat","SorteerCriterium","EnkelvoudigeRegelVersieConditie",
}

# Bewust géén eigen construct in het semantisch model.
BUITEN_SCOPE = {
    # beslistabel: genormaliseerd naar gewone Regels
    "Beslistabel","BeslistabelVersie","BeslistabelVersieHierarchisch","BtRij","BtTerm","BtConjunctie",
    "BtConditieCell","BtConclusieCell","BtConditieCase","BtConclusieCase","BtExpressieCase",
    "BtAttribuutConditie","BtAttribuutConclusie","BtBoolConditie","BtBegrenzing","BtConditieVar",
    "BtConclusieVar","BtExpressieVar","NoConclusie","NietVanToepassing",
    # linguïstiek / layout (ITaalkundig, Semantiekloos)
    "Werkwoord","SterkeWerkwoordVervoeging","ZwakkeWerkwoordVervoeging","OnregelmatigWerkwoordVervoeging",
    "Lezing","Koptekst","Woordenlijst",
    # servicegrens / berichten (servicespraak, marshalling) + service-tests
    "ElementairTestBerichtVeld","ComplexTestBerichtVeld","ElementaireVeldVerwachting",
    "ComplexeVeldVerwachting","InvoerSubBericht","UitvoerSubBericht","TestInvoerBericht",
    "TestUitvoerBericht","ServiceTest","ServiceTestSet","ServiceInvoerTest","TeTestenFlow",
    "ObjectReference","ObjectListLiteral","PeriodeTestBericht","PeriodeVerwachting",
    "TijdsafhankelijkTestBerichtVeld","TijdsafhankelijkeVeldverwachting","TenMinsteDatumTijdLiteral",
    "TeTestenEigenschapRegels","VerwachtFoutAttribute",
    "ServiceveldRef","ServiceTestRef","ServiceUitvoerTest","ServiceInvoerTest","IAbstractServiceTest",
    "TestInitialisatie","TeTestenRegelGroepEigenschap","InterpreterOnlyAttribute","ITeTestenEenheid",
    # abstracte basisconcepten (concrete subtypes zijn wel gedekt)
    "Actie","Conditie","Predicaat","OnderwerpExpressie","ContextOngevoeligeLiteral",
    "BtConditie","BtConclusie","BtKenmerkConclusie",
    # linguïstiek
    "WerkwoordPredicaat",
}

def scan(root):
    counts = collections.Counter()
    files = glob.glob(os.path.join(root, "solutions/**/*.mps"), recursive=True)
    for f in files:
        try:
            r = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        idx = {c.get("index"): c.get("name") for c in r.iter("concept") if c.get("name")}
        for n in r.iter("node"):
            fq = idx.get(n.get("concept"))
            if fq and fq.split(".structure.")[0] in LANGS:
                counts[fq] += 1
    return counts, len(files)

def main():
    counts, nfiles = scan(ROOT)
    per = {"GEDEKT": [], "BUITEN SCOPE / GENORMALISEERD": [], "NOG TE DOEN": []}
    for fq, c in counts.items():
        short = fq.rsplit(".", 1)[-1]
        bucket = "GEDEKT" if short in GEDEKT else ("BUITEN SCOPE / GENORMALISEERD" if short in BUITEN_SCOPE else "NOG TE DOEN")
        per[bucket].append((c, fq))
    tot = sum(counts.values())
    print(f"gescand: {nfiles} modellen, {len(counts)} concepten, {tot} node-gebruiken\n")
    for bucket in ("GEDEKT", "BUITEN SCOPE / GENORMALISEERD", "NOG TE DOEN"):
        items = sorted(per[bucket], reverse=True)
        n = sum(c for c, _ in items)
        print(f"== {bucket}: {len(items)} concepten, {n} gebruiken ({100*n/tot:.1f}%) ==")
        for c, fq in items:
            print(f"  {c:6d}  {fq}")
        print()

if __name__ == "__main__":
    main()
