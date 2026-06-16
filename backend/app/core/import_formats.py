from app.schemas.common import ImportFormatField, ImportFormatResponse, ImportRequiredScope


PRODUCT_IMPORT_FORMAT = ImportFormatResponse(
    entity="products",
    fields=[
        ImportFormatField(name="import_key", label="Import Key", required=False, required_scope=ImportRequiredScope.never, description="Idempotent upsert key. If matched, updates the existing product.", example="prod-001"),
        ImportFormatField(name="legacy_code", label="Legacy Code", required=False, required_scope=ImportRequiredScope.never, description="Legacy system code.", example="LEG-001"),
        ImportFormatField(name="category_code", label="Category Code", required=False, required_scope=ImportRequiredScope.never, description="Product category code.", example="frozen"),
        ImportFormatField(name="product_type_code", label="Product Type Code", required=False, required_scope=ImportRequiredScope.never, description="Product type code.", example="standard"),
        ImportFormatField(name="name", label="Name", required=True, required_scope=ImportRequiredScope.create, description="Display name of the product.", example="Imported Product"),
        ImportFormatField(name="name_kana", label="Name Kana", required=False, required_scope=ImportRequiredScope.never, description="Kana reading of the product name.", example="インポートショウヒン"),
        ImportFormatField(name="name_kana_key", label="Name Kana Key", required=False, required_scope=ImportRequiredScope.never, description="Kana search key.", example="インホト"),
        ImportFormatField(name="legacy_unit_code", label="Legacy Unit Code", required=False, required_scope=ImportRequiredScope.never, description="Legacy unit code.", example="CS"),
        ImportFormatField(name="pack_size", label="Pack Size", required=False, required_scope=ImportRequiredScope.never, description="Pack size as integer.", example=10),
        ImportFormatField(name="tax_category_code", label="Tax Category Code", required=False, required_scope=ImportRequiredScope.never, description="Tax category code.", example="taxable"),
        ImportFormatField(name="inventory_category_code", label="Inventory Category Code", required=False, required_scope=ImportRequiredScope.never, description="Inventory category code.", example="stock"),
        ImportFormatField(name="owner_code", label="Owner Code", required=False, required_scope=ImportRequiredScope.never, description="Owner or principal code.", example="OWN-01"),
        ImportFormatField(name="origin_code", label="Origin Code", required=False, required_scope=ImportRequiredScope.never, description="Origin code.", example="JP"),
        ImportFormatField(name="jan_code", label="JAN Code", required=False, required_scope=ImportRequiredScope.never, description="Barcode / JAN code.", example="4901234567890"),
        ImportFormatField(name="sales_price", label="Sales Price", required=False, required_scope=ImportRequiredScope.never, description="Base sales price.", example=1000),
        ImportFormatField(name="sales_price_1", label="Sales Price 1", required=False, required_scope=ImportRequiredScope.never, description="Tier sales price 1.", example=950),
        ImportFormatField(name="sales_price_2", label="Sales Price 2", required=False, required_scope=ImportRequiredScope.never, description="Tier sales price 2.", example=900),
        ImportFormatField(name="sales_price_3", label="Sales Price 3", required=False, required_scope=ImportRequiredScope.never, description="Tier sales price 3.", example=850),
        ImportFormatField(name="sales_price_4", label="Sales Price 4", required=False, required_scope=ImportRequiredScope.never, description="Tier sales price 4.", example=800),
        ImportFormatField(name="sales_price_5", label="Sales Price 5", required=False, required_scope=ImportRequiredScope.never, description="Tier sales price 5.", example=750),
        ImportFormatField(name="sales_price_6", label="Sales Price 6", required=False, required_scope=ImportRequiredScope.never, description="Tier sales price 6.", example=700),
        ImportFormatField(name="purchase_price", label="Purchase Price", required=False, required_scope=ImportRequiredScope.never, description="Purchase price.", example=650),
        ImportFormatField(name="inventory_price", label="Inventory Price", required=False, required_scope=ImportRequiredScope.never, description="Inventory valuation price.", example=650),
        ImportFormatField(name="list_price", label="List Price", required=False, required_scope=ImportRequiredScope.never, description="List price.", example=1200),
        ImportFormatField(name="tax_rate_code", label="Tax Rate Code", required=False, required_scope=ImportRequiredScope.never, description="Tax rate code.", example="10pct"),
        ImportFormatField(name="handling_category_code", label="Handling Category Code", required=False, required_scope=ImportRequiredScope.never, description="Handling category code.", example="frozen"),
        ImportFormatField(name="name_en", label="Name EN", required=False, required_scope=ImportRequiredScope.never, description="English product name.", example="Imported Product"),
        ImportFormatField(name="name_zh_hk", label="Name ZH HK", required=False, required_scope=ImportRequiredScope.never, description="Traditional Chinese product name.", example="匯入商品"),
        ImportFormatField(name="customs_reference_price", label="Customs Reference Price", required=False, required_scope=ImportRequiredScope.never, description="Reference price for customs.", example=680),
        ImportFormatField(name="freight_weight", label="Freight Weight", required=False, required_scope=ImportRequiredScope.never, description="Freight weighting factor for HKD draft cost calculation.", example=0.5),
        ImportFormatField(name="customs_origin_text", label="Customs Origin Text", required=False, required_scope=ImportRequiredScope.never, description="Origin text for customs documents.", example="Japan"),
        ImportFormatField(name="remarks", label="Remarks", required=False, required_scope=ImportRequiredScope.never, description="Free text remarks.", example="Seasonal item"),
        ImportFormatField(name="chayafuda_flag", label="Chayafuda Flag", required=False, required_scope=ImportRequiredScope.never, description="Chayafuda handling flag.", example=False),
        ImportFormatField(name="application_category_code", label="Application Category Code", required=False, required_scope=ImportRequiredScope.never, description="Application category code.", example="retail"),
        ImportFormatField(name="order_uom", label="Order UOM", required=True, required_scope=ImportRequiredScope.create, description="Order unit of measure.", example="count"),
        ImportFormatField(name="purchase_uom", label="Purchase UOM", required=True, required_scope=ImportRequiredScope.create, description="Purchase unit of measure.", example="count"),
        ImportFormatField(name="invoice_uom", label="Invoice UOM", required=True, required_scope=ImportRequiredScope.create, description="Invoice unit of measure.", example="count"),
        ImportFormatField(name="is_catch_weight", label="Catch Weight", required=False, required_scope=ImportRequiredScope.never, description="Whether the product uses catch weight.", example=False),
        ImportFormatField(name="weight_capture_required", label="Weight Capture Required", required=False, required_scope=ImportRequiredScope.never, description="Whether weight capture is required.", example=False),
        ImportFormatField(name="pricing_basis_default", label="Default Pricing Basis", required=False, required_scope=ImportRequiredScope.never, description="Default pricing basis enum.", example="uom_count"),
        ImportFormatField(name="active", label="Active", required=False, required_scope=ImportRequiredScope.never, description="Active flag.", example=True),
    ],
)

CUSTOMER_IMPORT_FORMAT = ImportFormatResponse(
    entity="customers",
    fields=[
        ImportFormatField(name="import_key", label="Import Key", required=False, required_scope=ImportRequiredScope.never, description="Idempotent upsert key. If matched, updates the existing customer.", example="cust-001"),
        ImportFormatField(name="region", label="Region", required=False, required_scope=ImportRequiredScope.never, description="Customer region text.", example="kanto"),
        ImportFormatField(name="name", label="Name", required=True, required_scope=ImportRequiredScope.create, description="Customer display name.", example="テスト顧客"),
        ImportFormatField(name="active", label="Active", required=False, required_scope=ImportRequiredScope.never, description="Active flag.", example=True),
    ],
)

SUPPLIER_IMPORT_FORMAT = ImportFormatResponse(
    entity="suppliers",
    fields=[
        ImportFormatField(name="import_key", label="Import Key", required=False, required_scope=ImportRequiredScope.never, description="Idempotent upsert key. If matched, updates the existing supplier.", example="sup-001"),
        ImportFormatField(name="name", label="Name", required=True, required_scope=ImportRequiredScope.create, description="Supplier display name.", example="テスト仕入先"),
        ImportFormatField(name="active", label="Active", required=False, required_scope=ImportRequiredScope.never, description="Active flag.", example=True),
    ],
)
