"""
Visual type registries, connector maps, and lookup tables.

This module centralizes all static lookup data including:
- Power Query connector function mappings
- Visual type color schemes and abbreviations
- Namespace-to-category fallbacks
"""

from pbip_documenter.config import C

# ═══════════════════════════════════════════════════════════════════════════
# Connector Registry
# Maps Power Query function names to (friendly_label, category)
# ═══════════════════════════════════════════════════════════════════════════
CONNECTOR_MAP = {
    # SharePoint connectors
    "SharePoint.Tables": ("SharePoint Lists", "SharePoint"),
    "SharePoint.Files": ("SharePoint Files", "SharePoint"),
    "SharePoint.Contents": ("SharePoint Library", "SharePoint"),
    # SQL connectors
    "Sql.Database": ("SQL Server", "SQL"),
    "Sql.Databases": ("SQL Server", "SQL"),
    "AzureSQL.Database": ("Azure SQL", "Azure"),
    "AzureSynapseAnalytics": ("Azure Synapse", "Azure"),
    "Synapse.Warehouse": ("Synapse Warehouse", "Azure"),
    "AnalysisServices.Database": ("SSAS", "SQL"),
    # Azure data connectors
    "AzureStorage.Blobs": ("Azure Blob Storage", "Azure"),
    "AzureStorage.BlobContents": ("Azure Blob Storage", "Azure"),
    "AzureBlobStorage.Contents": ("Azure Blob Storage", "Azure"),
    "AzureStorage.Tables": ("Azure Table Storage", "Azure"),
    "AzureDataLake.Filesystem": ("Azure Data Lake", "Azure"),
    "AzureDataLakeStorage.Filesystem": ("ADLS Gen2", "Azure"),
    "AzureAnalysisServices.Database": ("Azure AS", "Azure"),
    # Cloud data platforms
    "Snowflake.Databases": ("Snowflake", "Cloud"),
    "Databricks.Catalogs": ("Databricks", "Cloud"),
    "Databricks.Query": ("Databricks", "Cloud"),
    "GoogleBigQuery.Database": ("BigQuery", "Cloud"),
    "GoogleAnalytics.Accounts": ("Google Analytics", "Cloud"),
    "Salesforce.Data": ("Salesforce", "Cloud"),
    "Salesforce.Reports": ("Salesforce", "Cloud"),
    "Dynamics365.Accounts": ("Dynamics 365", "Cloud"),
    "CommonDataService.Database": ("Dataverse", "Cloud"),
    "PowerPlatform.Dataflows": ("Power Platform Dataflows", "Cloud"),
    "PowerBI.Datasets": ("Power BI Dataset", "Cloud"),
    "AmazonRedshift.Database": ("Amazon Redshift", "Cloud"),
    "AmazonAthena.Tables": ("Amazon Athena", "Cloud"),
    # Traditional databases
    "PostgreSQL.Database": ("PostgreSQL", "SQL"),
    "MySQL.Database": ("MySQL", "SQL"),
    "Oracle.Database": ("Oracle", "SQL"),
    "Teradata.Database": ("Teradata", "SQL"),
    "DB2.Database": ("IBM Db2", "SQL"),
    "SapHana.Database": ("SAP HANA", "SQL"),
    "SapBusinessWarehouse.Cubes": ("SAP BW", "SQL"),
    # File connectors
    "Excel.Workbook": ("Excel File", "File"),
    "Excel.CurrentWorkbook": ("Excel (current)", "File"),
    "Csv.Document": ("CSV File", "File"),
    "Json.Document": ("JSON File", "File"),
    "Xml.Document": ("XML File", "File"),
    "Pdf.Tables": ("PDF File", "File"),
    "Folder.Files": ("Local Folder", "File"),
    "File.Contents": ("Local File", "File"),
    # Web/REST connectors
    "OData.Feed": ("OData Feed", "Web"),
    "Web.Contents": ("Web / REST API", "Web"),
    "Web.Page": ("Web Page", "Web"),
    # Other connectors
    "ActiveDirectory.Domains": ("Active Directory", "Other"),
    "Lakehouse.Contents": ("Fabric Lakehouse", "Cloud"),
    "Warehouse.Contents": ("Fabric Warehouse", "Cloud"),
}

# Prefixes that indicate transform functions, not data connectors
_NON_CONN = (
    "Table.",
    "List.",
    "Record.",
    "Text.",
    "Number.",
    "Date.",
    "DateTime.",
    "DateTimeZone.",
    "Duration.",
    "Binary.",
    "Json.",
    "Xml.",
    "Csv.",
    "Excel.CurrentWorkbook",
    "Value.",
    "Type.",
    "Function.",
    "Splitter.",
    "Replacer.",
    "Comparer.",
    "Combiner.",
    "BinaryEncoding.",
    "Compression.",
)

# Namespace to category fallback mapping
_NS_CAT = {
    # SQL family
    "Sql": "SQL",
    "AzureSQL": "Azure",
    "AzureSynapseAnalytics": "Azure",
    "AnalysisServices": "SQL",
    # Azure family
    "AzureStorage": "Azure",
    "AzureBlobStorage": "Azure",
    "AzureDataLake": "Azure",
    "AzureDataLakeStorage": "Azure",
    "AzureAnalysisServices": "Azure",
    # Cloud platforms
    "Snowflake": "Cloud",
    "Databricks": "Cloud",
    "GoogleBigQuery": "Cloud",
    "GoogleAnalytics": "Cloud",
    "Salesforce": "Cloud",
    "Dynamics365": "Cloud",
    "CommonDataService": "Cloud",
    "PowerPlatform": "Cloud",
    "Fabric": "Cloud",
    "Lakehouse": "Cloud",
    "Warehouse": "Cloud",
    "AmazonRedshift": "Cloud",
    # Microsoft services
    "SharePoint": "SharePoint",
    # Traditional databases
    "Oracle": "SQL",
    "PostgreSQL": "SQL",
    "MySQL": "SQL",
    "Teradata": "SQL",
    "DB2": "SQL",
    "SapHana": "SQL",
    # Web/File
    "OData": "Web",
    "Web": "Web",
    "Excel": "File",
    "Folder": "File",
    "File": "File",
    "ActiveDirectory": "Other",
}

# ═══════════════════════════════════════════════════════════════════════════
# Visual Type Registry
# ═══════════════════════════════════════════════════════════════════════════

# Short abbreviations for narrow wireframe boxes
_TYPE_ABBREV = {
    # Charts
    "Slicer": "Slicer",
    "Bar Chart": "Bar",
    "Column Chart": "Col",
    "Line Chart": "Line",
    "Area Chart": "Area",
    "Combo Chart": "Combo",
    "Donut Chart": "Donut",
    "Pie Chart": "Pie",
    "Scatter": "Scatter",
    "Waterfall": "Wtrfl",
    "Funnel": "Funnel",
    "Treemap": "Tree",
    # Tables
    "Pivot Table": "Table",
    "Table": "Table",
    # Cards/KPIs
    "Card": "Card",
    "Multi-Row Card": "Cards",
    "KPI": "KPI",
    "Gauge": "Gauge",
    "Scorecard": "Score",
    # UI elements
    "Button": "Btn",
    "Navigator": "Nav",
    "Bookmark Nav": "BkNav",
    # Custom
    "Custom Visual": "Custom",
    "Custom Chart": "Custom",
    "Custom Pivot": "Custom",
    "Custom Map": "Custom",
    "Custom KPI": "Custom",
    "Custom Table": "Custom",
}

# Visual registry: type_key -> (friendly_name, border_color, fill_color)
_VD = {
    # Slicers
    "slicer": ("Slicer", C.RUBINE, "FCEEF5"),
    "advancedSlicerVisual": ("Slicer", C.RUBINE, "FCEEF5"),
    "listSlicer": ("Slicer", C.RUBINE, "FCEEF5"),
    # Charts (blue family)
    "barChart": ("Bar Chart", C.PACIFIC, "E0E8F5"),
    "columnChart": ("Column Chart", C.PACIFIC, "E0E8F5"),
    "clusteredBarChart": ("Bar Chart", C.PACIFIC, "E0E8F5"),
    "clusteredColumnChart": ("Column Chart", C.PACIFIC, "E0E8F5"),
    "lineChart": ("Line Chart", C.PACIFIC, "E0E8F5"),
    "areaChart": ("Area Chart", C.PACIFIC, "E0E8F5"),
    "stackedBarChart": ("Stacked Bar", C.PACIFIC, "E0E8F5"),
    "stackedColumnChart": ("Stacked Column", C.PACIFIC, "E0E8F5"),
    "lineClusteredColumnComboChart": ("Combo Chart", C.PACIFIC, "E0E8F5"),
    "lineStackedColumnComboChart": ("Combo Chart", C.PACIFIC, "E0E8F5"),
    "ribbonChart": ("Ribbon Chart", C.PACIFIC, "E0E8F5"),
    "waterfallChart": ("Waterfall", C.PACIFIC, "E0E8F5"),
    "funnelChart": ("Funnel", C.PACIFIC, "E0E8F5"),
    "scatterChart": ("Scatter", C.PACIFIC, "E0E8F5"),
    "donutChart": ("Donut Chart", C.PACIFIC, "E0E8F5"),
    "pieChart": ("Pie Chart", C.PACIFIC, "E0E8F5"),
    "map": ("Map", C.PACIFIC, "E0E8F5"),
    "filledMap": ("Filled Map", C.PACIFIC, "E0E8F5"),
    "treemap": ("Treemap", C.PACIFIC, "E0E8F5"),
    "decompositionTreeVisual": ("Decomp. Tree", C.PACIFIC, "E0E8F5"),
    "flowMap": ("Flow Map", C.PACIFIC, "E0E8F5"),
    "arcGISMap": ("ArcGIS Map", C.PACIFIC, "E0E8F5"),
    "qnaVisual": ("Q&A", C.PACIFIC, "E0E8F5"),
    "paginated-report-visual": ("Paginated Report", C.PACIFIC, "E0E8F5"),
    # Tables (green family)
    "pivotTable": ("Pivot Table", C.EVERGREEN, "EDF8EB"),
    "tableEx": ("Table", C.EVERGREEN, "EDF8EB"),
    # Cards/KPIs (sky blue family)
    "card": ("Card", C.SKY, "E0F2FA"),
    "cardVisual": ("Card", C.SKY, "E0F2FA"),
    "multiRowCard": ("Multi-Row Card", C.SKY, "E0F2FA"),
    "kpi": ("KPI", C.SKY, "E0F2FA"),
    "gauge": ("Gauge", C.SKY, "E0F2FA"),
    "scorecard": ("Scorecard", C.SKY, "E0F2FA"),
    # Buttons/Navigation (gold family)
    "actionButton": ("Button", C.MARIGOLD, "FFF8E0"),
    "button": ("Button", C.MARIGOLD, "FFF8E0"),
    "reportPageNavigator": ("Navigator", C.MARIGOLD, "FFF8E0"),
    "bookmarkNavigator": ("Bookmark Nav", C.MARIGOLD, "FFF8E0"),
    # Advanced/Custom (gray family)
    "htmlContent": ("HTML Content", C.DGRAY, "F5F5F5"),
    "r-script-visual": ("R Visual", C.DGRAY, "F5F5F5"),
    "pythonVisual": ("Python Visual", C.DGRAY, "F5F5F5"),
    # Decorative (gray family)
    "textbox": ("Text Box", C.DGRAY, "F5F5F5"),
    "text": ("Text Box", C.DGRAY, "F5F5F5"),
    "image": ("Image", C.DGRAY, "F5F5F5"),
    "shape": ("Shape", C.DGRAY, "F5F5F5"),
    "basicShape": ("Shape", C.DGRAY, "F5F5F5"),
    "rectangle": ("Shape", C.DGRAY, "F5F5F5"),
    "line": ("Shape", C.DGRAY, "F5F5F5"),
}

# Visual type sets for classification
_DECO_VTS = {"shape", "basicShape", "image", "textbox", "text", "rectangle", "line", "group", "groupContainer"}

_SLICER_VTS = {"slicer", "advancedSlicerVisual", "listSlicer"}
_BTN_VTS = {"actionButton", "button"}
_UNKNOWN = {"", "unknown", "(not found)", "null", "none"}
