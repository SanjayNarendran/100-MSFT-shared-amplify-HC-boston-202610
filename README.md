# 100-MSFT-shared-amplify-HC-boston-202610

Hospital quality data published by the Centers for Medicare & Medicaid Services (CMS), packaged as CSV files together with everything needed to load it into **Microsoft Fabric**: a lakehouse, a load notebook, and a Direct Lake semantic model.

This README is written for people and for automated agents (bots). If you are an agent, read [Instructions for AI agents](#instructions-for-ai-agents) first.

## Contents

| Dataset | Folder | Subject | Files | Reporting periods covered |
|---|---|---|---|---|
| HCAHPS | [data/HCAHPS](data/HCAHPS) | Hospital patient experience survey (nurse and doctor communication, cleanliness, quietness, star ratings and similar) | 7 | 2019 to Mar 2025 |
| HAI | [data/HAI](data/HAI) | Healthcare Associated Infections (central line bloodstream, catheter urinary tract, surgical site, MRSA, C. diff) compared with the national benchmark | 7 | 2019 to Mar 2025 |
| PSI | [data/PSI](data/PSI) | Patient Safety Indicators (pressure ulcer, iatrogenic pneumothorax, falls with fracture, post-operative complications, PSI 90 composite) | 6 | Jul 2016 to Jun 2024 |

Every file has a `Facility ID` column (the 6 character CMS Certification Number) that identifies the hospital and joins the three datasets.

## Repository layout

```
data/                         CSV files, one sub-folder per dataset (stored with Git LFS)
  HCAHPS/  HAI/  PSI/
notebooks/load_cms_tables.ipynb          Spark notebook: raw CSVs -> lakehouse tables
semantic_model/CMS.SemanticModel/        Direct Lake semantic model in TMDL format
scripts/deploy_fabric.py                 Automates the whole Fabric deployment
scripts/requirements.txt                 Python dependencies for the script
```

## Get the files

The CSV files are stored with [Git LFS](https://git-lfs.com/). A plain `git clone` only downloads small pointer files, so run `git lfs pull` as well.

```bash
git lfs install
git clone https://github.com/<owner>/100-MSFT-shared-amplify-HC-boston-202610.git   # use this repository's URL
cd 100-MSFT-shared-amplify-HC-boston-202610
git lfs pull
```

Download only one dataset (git 2.25 or later):

```bash
git clone --filter=blob:none --sparse https://github.com/<owner>/100-MSFT-shared-amplify-HC-boston-202610.git
cd 100-MSFT-shared-amplify-HC-boston-202610
git sparse-checkout set data/HCAHPS
git lfs pull --include="data/HCAHPS/*"
```

## The data

All files are UTF-8, comma delimited, with a header row. Text is quoted with `"` and an embedded quote is written as `""`. Each file holds one CMS release; each row is one hospital and one measure.

Column names changed between releases (`City` became `City/Town`, `County Name` became `County/Parish`, and so on). Always match columns by name, never by position.

Read `Facility ID` as text, because values such as `010001` have a leading zero. Dates are `MM/DD/YYYY`. Expect the text values `Not Available` and `Not Applicable` and empty cells in numeric columns.

### HCAHPS (`data/HCAHPS/`)

Hospital Consumer Assessment of Healthcare Providers and Systems patient survey results.
Key columns: `Facility ID`, `Facility Name`, `State`, `HCAHPS Measure ID`, `HCAHPS Question`, `HCAHPS Answer Description`, `Patient Survey Star Rating`, `HCAHPS Answer Percent`, `HCAHPS Linear Mean Value`, `Number of Completed Surveys`, `Survey Response Rate Percent`, `Start Date`, `End Date`.
The latest file has 68 distinct `HCAHPS Measure ID` values.

### HAI (`data/HAI/`)

Healthcare Associated Infections in long format: several rows per hospital, one per statistic (for example `HAI_1_SIR`, `HAI_1_NUMERATOR`, `HAI_1_DOPC`, `HAI_1_CILOWER`, `HAI_1_CIUPPER`).
Key columns: `Facility ID`, `Facility Name`, `State`, `Measure ID`, `Measure Name`, `Compared to National`, `Score`, `Footnote`, `Start Date`, `End Date`.
`Compared to National` is one of `Better than the National Benchmark`, `No Different than National Benchmark`, `Worse than the National Benchmark`, `Not Available`.

### PSI (`data/PSI/`)

Patient Safety Indicators, one row per hospital per indicator (`PSI_03`, `PSI_06`, `PSI_08` ... `PSI_15`, `PSI_90`).
Key columns: `Facility ID`, `Facility Name`, `State`, `Measure ID`, `Measure Name`, `Rate`, `Footnote`, `Start Date`, `End Date`.
The oldest file (`CMS_PSI_6_decimal_file_04_20.csv`) uses a different naming scheme (`PSI-6` style ids and plain language measure names), so it is kept as raw data but not loaded into the lakehouse tables.

### File names and reporting periods

The month and year in a file name are only a release label. The reporting period of the data is in the `Start Date` and `End Date` columns of each file, and that is what the load notebook uses (`REPORTYEAR` = year of `End Date`).

| File | Reporting period | Loaded as `REPORTYEAR` |
|---|---|---|
| `data/HCAHPS/HCAHPS-Hospital_07_20.csv` | 01/01/2019 - 12/31/2019 | 2019 |
| `data/HCAHPS/HCAHPS-Hospital_10_21.csv` | 07/01/2020 - 12/31/2020 | 2020 |
| `data/HCAHPS/HCAHPS-Hospital_10_22.csv` | 01/01/2021 - 12/31/2021 | 2021 |
| `data/HCAHPS/HCAHPS-Hospital_11_23.csv` | 01/01/2022 - 12/31/2022 | 2022 |
| `data/HCAHPS/HCAHPS-Hospital_10_24.csv` | 01/01/2023 - 12/31/2023 | 2023 |
| `data/HCAHPS/HCAHPS-Hospital_11_2025.csv` | 01/01/2024 - 12/31/2024 | 2024 |
| `data/HCAHPS/HCAHPS-Hospital_02_2026.csv` | 04/01/2024 - 03/31/2025 | 2025 |
| `data/HAI/Healthcare_Associated_Infections-Hospital_04_21.csv` | 01/01/2019 - 12/31/2019 | 2019 |
| `data/HAI/Healthcare_Associated_Infections-Hospital_10_21.csv` | 07/01/2019 - 12/31/2020 | 2020 |
| `data/HAI/Healthcare_Associated_Infections-Hospital_10_22.csv` | 01/01/2021 - 12/31/2021 | 2021 |
| `data/HAI/Healthcare_Associated_Infections-Hospital_11_23.csv` | 01/01/2022 - 12/31/2022 | 2022 |
| `data/HAI/Healthcare_Associated_Infections-Hospital_10_24.csv` | 01/01/2023 - 12/31/2023 | 2023 |
| `data/HAI/Healthcare_Associated_Infections-Hospital_11_2025.csv` | 01/01/2024 - 12/31/2024 | 2024 |
| `data/HAI/Healthcare_Associated_Infections-Hospital_2026_2.csv` | 04/01/2024 - 03/31/2025 | 2025 |
| `data/PSI/CMS_PSI_6_decimal_file_04_20.csv` | 07/01/2016 - 06/30/2018 | not loaded (old layout) |
| `data/PSI/CMS_PSI_6_decimal_file_04_22.csv` | 07/01/2018 - 12/31/2019 | 2019 |
| `data/PSI/CMS_PSI_6_decimal_file_11_23.csv` | 07/01/2019 - 06/30/2021 | 2021 |
| `data/PSI/CMS_PSI_6_decimal_file_07_24.csv` | 07/01/2020 - 06/30/2022 | 2022 |
| `data/PSI/CMS_PSI_6_decimal_file_08.csv` | 07/01/2021 - 06/30/2023 | 2023 |
| `data/PSI/CMS_PSI_6_decimal_file.csv` | 07/01/2022 - 06/30/2024 | 2024 |

## Deploy to Microsoft Fabric

### What gets created

All items are created in one existing Fabric workspace, whose name you provide.

| Item | Default name | Description |
|---|---|---|
| Lakehouse | `lh_amplify_hc` | Holds the raw files and the tables. Created without schemas, so tables are under `Tables/`. |
| Raw files | `Files/raw/HCAHPS`, `Files/raw/HAI`, `Files/raw/PSI` | The 20 CSV files, with the same sub-folders as `data/`. |
| Notebook | `nb_load_cms_tables` | PySpark notebook that reads `Files/raw` and writes the Delta tables. |
| Tables | `psi90`, `hai`, `hcahps`, `dim_date` | One wide row per hospital per release, plus a calendar table. Spark stores table names in lower case. |
| Semantic model | `CMS` | Direct Lake model over the lakehouse tables, with relationships. |

### Prerequisites

- An existing Fabric workspace on a Fabric capacity (trial or F SKU) where you have the **Contributor**, **Member** or **Admin** role.
- Python 3.10 or later and the Azure CLI (`az login`), or a service principal that has access to the workspace.
- The tenant setting "Users can access data stored in OneLake with apps external to Fabric" must be enabled (it is on by default). The script uploads files through the OneLake API.
- The CSV files downloaded with `git lfs pull` (see [Get the files](#get-the-files)).

### Option A: automated (recommended)

Only the workspace name is needed.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r scripts/requirements.txt
az login                             # or set AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
python scripts/deploy_fabric.py --workspace "<YOUR FABRIC WORKSPACE NAME>"
```

The script looks up the workspace by name (no ids are hard-coded) and runs these steps in order. Every step can be repeated safely; existing items are updated or skipped.

| Step | What it does |
|---|---|
| `lakehouse` | Creates the lakehouse `lh_amplify_hc`. |
| `upload` | Uploads `data/<DATASET>/*.csv` to `Files/raw/<DATASET>/` through the OneLake API. Skips files that are already there with the same size. |
| `notebook` | Creates or updates the notebook from `notebooks/load_cms_tables.ipynb` and attaches the lakehouse as its default lakehouse. |
| `run` | Runs the notebook and waits for it (about 4 to 8 minutes, most of it Spark start-up). |
| `model` | Creates or updates the `CMS` semantic model from `semantic_model/CMS.SemanticModel`, then refreshes it. |
| `verify` | Queries the model and compares row counts with the expected values below. |

Options: `--lakehouse`, `--notebook`, `--model` change the item names, and `--steps lakehouse,upload` (a comma separated list) runs only some steps.

### Option B: manual, in the Fabric portal

1. **Create the lakehouse.** In the workspace choose **New item > Lakehouse**, name it `lh_amplify_hc`, and leave "Lakehouse schemas" unchecked.
2. **Upload the files.** Open the lakehouse. In the Explorer, right-click **Files > New subfolder** and create `raw`. Inside `raw` create the sub-folders `HCAHPS`, `HAI` and `PSI`. For each sub-folder choose **Upload > Upload files** and select the CSV files of the matching folder in `data/`. (OneLake file explorer or Azure Storage Explorer also work.) Keep the file names unchanged.
3. **Create the notebook and load the tables.** In the workspace choose **Import > Notebook > From this computer** and select `notebooks/load_cms_tables.ipynb`. Open it, and in the Explorer pane choose **Add data items > Existing data sources** and add `lh_amplify_hc` so that it is the default lakehouse. Select **Run all**. When it finishes, refresh the lakehouse; `psi90`, `hai`, `hcahps` and `dim_date` appear under Tables.
4. **Create the semantic model.**
   - Easiest and exact: run only the model step of the script, `python scripts/deploy_fabric.py --workspace "<NAME>" --steps model`.
   - By hand in the portal: open the lakehouse, choose **New semantic model**, name it `CMS`, select `psi90`, `hai`, `hcahps` and `dim_date`, and confirm. Open the model and create the two table relationships described in [The semantic model](#the-semantic-model). In this route the columns keep their physical names (for example `HAI_1_SIR_Central_Line_Associated_Bloodstream_Infection_ICU_select_Wards`); the script route restores the readable names and the date relationships.
5. **Check the result** against the numbers in [Verify the result](#verify-the-result).

### Verify the result

Row counts that the semantic model must return for the data in this repository (the `verify` step checks the totals):

| Table | Total rows | By `REPORTYEAR` |
|---|---|---|
| `PSI90` | 23,846 | 2019: 4,813 / 2021: 4,794 / 2022: 4,759 / 2023: 4,723 / 2024: 4,757 |
| `HAI` | 33,800 | 2019: 4,912 / 2020: 4,855 / 2021: 4,845 / 2022: 4,829 / 2023: 4,779 / 2024: 4,791 / 2025: 4,789 |
| `HCAHPS` | 22,440 | 2019: 3,465 / 2020: 2,855 / 2021: 3,291 / 2022: 3,273 / 2023: 3,207 / 2024: 3,166 / 2025: 3,183 |

Useful DAX test in the semantic model: `EVALUATE ROW("rows", COUNTROWS(HAI))` returns 33800. If you added or removed data files the totals change; that is expected.

### How the tables are built

The notebook turns the long CMS files (one row per hospital per measure) into wide tables (one row per hospital per release):

| Table | Source | Rows kept | Column for each measure | Value |
|---|---|---|---|---|
| `PSI90` | `raw/PSI` | measures with `Measure ID` like `PSI_%` | `Measure Name` (13 columns) | `Rate` |
| `HAI` | `raw/HAI` | all measures | `Measure ID` + `-` + `Measure Name` (36 columns) | `Score` |
| `HCAHPS` | `raw/HCAHPS` | measure ids containing `STAR_RATING` or `LINEAR_SCORE`; hospitals with no such value in a release are dropped | `HCAHPS Measure ID` + `-` + `HCAHPS Answer Description` (21 columns) | `Patient Survey Star Rating` for star rating measures, `HCAHPS Linear Mean Value` for linear score measures |

Rules that apply to all three tables:

- Non-numeric values (`Not Available`, `Not Applicable`) become null; numbers are `double`.
- Hospital attributes come from the file: `facility_id` (text), `facility_name`, `ADDRESS`, `CITY`, `STATE`, `zip_code`, `start_date`, `end_date` (dates).
- `REPORTYEAR` = year of `end_date` (as `double`). `FACILITYYEARKEY` = `facility_id` followed by `REPORTYEAR` as an integer, for example `0100012024`. It is unique per row.
- Physical column names contain only letters, digits and underscores because Delta/Spark does not allow spaces and punctuation: every run of other characters becomes `_`, and leading and trailing `_` are removed. The semantic model maps each physical column back to its readable name, such as `H_COMP_1_STAR_RATING-Nurse communication - star rating`.
- `dim_date` has one row per calendar day from 1 January of the earliest year to 31 December of the latest year found in the tables, with `Date`, `Year`, `MonthNo`, `Month`, `QuarterNo`, `Quarter` and `Day`.

The full list of columns, with readable names and types, is in `semantic_model/CMS.SemanticModel/definition/tables/`.

### The semantic model

`CMS` is a Direct Lake on OneLake model: it reads the Delta tables in place. Refresh the model after new data is loaded (the script does this).

**Tables**: `PSI90`, `HAI`, `HCAHPS` (fact tables, one row per hospital per release) and six hidden date tables `LocalDateTable_*`, all six reading `dim_date`.

**Relationships** (identical to the reference CMS model):

| From (one side) | To (many side) | Direction | Active |
|---|---|---|---|
| `PSI90[FACILITYYEARKEY]` | `HAI[FACILITYYEARKEY]` | both | yes |
| `PSI90[FACILITYYEARKEY]` | `HCAHPS[FACILITYYEARKEY]` | both | yes |
| `PSI90[start date]`, `PSI90[end date]` | each to its own hidden date table `[Date]` | single | yes |
| `HAI[start date]`, `HAI[end date]` | each to its own hidden date table `[Date]` | single | yes |
| `HCAHPS[start date]`, `HCAHPS[end date]` | each to its own hidden date table `[Date]` | single | yes |

`PSI90` is the one side of both table relationships. PSI data has no row for 2020 or 2025, so for those years the `HAI` and `HCAHPS` rows show blank `PSI90` values. Use `PSI90`, `HAI` and `HCAHPS` columns from the same `REPORTYEAR` for cross-dataset analysis.

**Measures**: the model contains no explicit DAX measures. Numeric columns summarise by sum, and all other columns are not summarised.

**Differences from the reference CMS model**: the tables read the lakehouse (Direct Lake) instead of an external warehouse; the six date tables read `dim_date` instead of being calculated (Direct Lake cannot use calculated tables that read its own tables); the Power BI Desktop date template table is omitted; compatibility level is 1604, which Direct Lake on OneLake requires. Tables, readable column names, data types, row counts and values were compared with the reference model and match.

### Loading new data

1. Download the new CMS file (see [Where to find newer data](#where-to-find-newer-data)) and put it in the matching `data/<DATASET>/` folder.
2. Run `python scripts/deploy_fabric.py --workspace "<NAME>" --steps upload,run,model,verify`, or upload the file to `Files/raw/<DATASET>/` by hand and run the notebook again.
3. The notebook rebuilds the tables from every file in `Files/raw`, so no other change is needed. Update the row counts in the Verify section.

## Instructions for AI agents

1. **Get the workspace name.** Ask the user for the display name of their Fabric workspace if it was not given. Do not guess it. Confirm it exists with `az rest --resource https://api.fabric.microsoft.com --url https://api.fabric.microsoft.com/v1/workspaces` or by running the script.
2. **Download the data.** `git lfs install`, clone this repository, then `git lfs pull`. Confirm `data/HCAHPS/*.csv` are real files (megabytes), not LFS pointers.
3. **Authenticate.** `az login` (or service principal environment variables) with a principal that has Contributor or higher on the workspace.
4. **Deploy.** `pip install -r scripts/requirements.txt` then `python scripts/deploy_fabric.py --workspace "<NAME>"`. The script is idempotent and is the reference implementation of the steps in Option B.
5. **Check.** The last lines must show `OK` for `PSI90: 23846`, `HAI: 33800` and `HCAHPS: 22440` (see [Verify the result](#verify-the-result)).
6. **Report** to the user the workspace, lakehouse, notebook and semantic model names created.

Things not to do: do not change table or column names (the semantic model depends on them), do not put workspace or lakehouse ids into this repository (the script resolves them at run time), and do not commit credentials.

Troubleshooting:

| Symptom | Cause and fix |
|---|---|
| `Workspace '...' not found` | Wrong name or no access. Names are case sensitive. |
| `The CSV files are Git LFS pointers` | Run `git lfs pull`. |
| 403 when uploading | You need Contributor on the workspace, and the OneLake external access tenant setting must be on. |
| `ItemDisplayNameNotAvailableYet` | A recently deleted item name is reserved for a few minutes. The script retries automatically. |
| Notebook status `Failed` | Open the run in the workspace Monitor hub. Usual causes are no Spark capacity or the lakehouse not set as default. |
| Model refresh fails on a missing table or column | The notebook has not finished or was not run. Run `--steps run,model`. |

## Where to find newer data

CMS publishes these datasets on the **Provider Data Catalog** (https://data.cms.gov/provider-data/). Each dataset page has a **Download** button for the CSV, and the catalog also offers an API. CMS refreshes the hospital data roughly every quarter.

| Dataset | CMS dataset |
|---|---|
| HCAHPS | **Patient survey (HCAHPS) - Hospital**: https://data.cms.gov/provider-data/dataset/dgck-syfz |
| HAI | **Healthcare Associated Infections - Hospital**: https://data.cms.gov/provider-data/dataset/77hc-ibv8 |
| PSI | **CMS Medicare PSI-90 and component measures - six-digit estimate dataset**: https://data.cms.gov/provider-data/dataset/muwa-iene |

- All hospital datasets: https://data.cms.gov/provider-data/topics/hospitals
- Older releases: the **Archived data** page of the Provider Data Catalog.
- Consumer view of the same quality data: https://www.medicare.gov/care-compare/

## Source and license

The data is produced by CMS and published at data.cms.gov. CMS data is generally in the public domain; check the terms on the dataset page before redistributing it. The scripts, notebook and model definition in this repository are provided as is, without warranty.
