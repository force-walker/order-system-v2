from datetime import UTC,date,datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes_related_documents import get_related_documents
from app.db.base import Base
from app.models.entities import (Customer,Delivery,DeliveryItem,Invoice,InvoiceItem,InvoiceStatus,Order,OrderItem,
    OrderStatus,PricingBasis,Product,PurchaseResult,PurchaseResultStatus,Supplier,SupplierAllocation,SupplierBill,
    SupplierBillItem,SupplierBillStatus)


engine=create_engine("sqlite+pysqlite:///:memory:",connect_args={"check_same_thread":False},poolclass=StaticPool)
Base.metadata.create_all(engine)


def _seed(db:Session):
    stamp=str(datetime.now(UTC).timestamp());customer=Customer(customer_code="C"+stamp,name="Customer",active=True)
    supplier=Supplier(supplier_code="S"+stamp,name="Supplier",active=True);product=Product(sku="P"+stamp,name="Fish",order_uom="piece",purchase_uom="piece",invoice_uom="piece",pricing_basis_default=PricingBasis.uom_count,active=True)
    db.add_all([customer,supplier,product]);db.flush();orders=[];items=[]
    for seq in (101,102):
        order=Order(document_seq=seq,next_line_no=20,order_no=f"ORD-T{seq}",customer_id=customer.id,order_datetime=datetime.now(UTC),delivery_date=date.today(),status=OrderStatus.invoiced);db.add(order);db.flush();orders.append(order)
        item=OrderItem(order_id=order.id,order_line_no=f"ODL-T{seq}",line_no=10,line_ref=f"ODL-T{seq}",product_id=product.id,ordered_qty=1,pricing_basis=PricingBasis.uom_count,unit_price_uom_count=10);db.add(item);db.flush();items.append(item)
    delivery=Delivery(document_seq=201,next_line_no=20,delivery_no="DEL-T201",order_id=orders[0].id,customer_id=customer.id,delivery_date=date.today(),shipped_date=date.today());db.add(delivery);db.flush()
    db.add(DeliveryItem(delivery_id=delivery.id,order_item_id=items[0].id,product_id=product.id,delivery_line_no="DLI-T201",line_no=10,line_ref="DLI-T201",delivered_qty=1,delivered_uom="piece",shipped_date=date.today()))
    invoice=Invoice(document_seq=301,next_line_no=30,invoice_no="IVD-T301",invoice_draft_no="IVD-T301",official_invoice_no=None,customer_id=customer.id,invoice_date=date.today(),delivery_date=date.today(),delivery_id=delivery.id,subtotal=20,tax_total=0,grand_total=20,status=InvoiceStatus.draft,is_locked=False);db.add(invoice);db.flush()
    for n,item in enumerate((items[0],items[0],items[1]),1):db.add(InvoiceItem(invoice_id=invoice.id,order_item_id=item.id,invoice_line_no=f"IVL-T{n}",line_no=n*10,line_ref=f"IVL-T{n}",billable_qty=1,billable_uom="piece",sales_unit_price=10,line_amount=10,tax_amount=0))
    allocation=SupplierAllocation(order_item_id=items[0].id,final_supplier_id=supplier.id,final_qty=1,final_uom="piece");db.add(allocation);db.flush();result=PurchaseResult(allocation_id=allocation.id,supplier_id=supplier.id,purchased_qty=1,purchased_uom="piece",unit_cost=5,result_status=PurchaseResultStatus.filled);db.add(result);db.flush()
    bill=SupplierBill(document_seq=401,next_line_no=20,bill_no="APB-T401",supplier_id=supplier.id,supplier_invoice_no="EXT-T401",bill_date=date.today(),currency="JPY",status=SupplierBillStatus.cancelled,subtotal=5,tax=0,adjustment=0,total_amount=5);db.add(bill);db.flush();db.add(SupplierBillItem(supplier_bill_id=bill.id,line_no=10,purchase_result_id=result.id,product_id=product.id,sku=product.sku,description=product.name,quantity=1,uom="piece",unit_cost=5,line_amount=5));db.commit()
    return orders,delivery,invoice,bill


def test_order_only_returns_no_missing_document_error():
    with Session(engine) as db:
        customer=Customer(customer_code="ONLY",name="Only",active=True);db.add(customer);db.flush();order=Order(document_seq=1,next_line_no=10,order_no="ORD-ONLY",customer_id=customer.id,order_datetime=datetime.now(UTC),delivery_date=date.today(),status=OrderStatus.new);db.add(order);db.commit()
        related=get_related_documents("order",order.id,db)
        assert [x.number for x in related.orders]==["ORD-ONLY"]
        assert related.deliveries==[] and related.invoices==[] and related.supplier_bills==[]


def test_related_documents_are_bidirectional_deduplicated_and_include_draft_cancelled():
    with Session(engine) as db:
        orders,delivery,invoice,bill=_seed(db)
        from_order=get_related_documents("order",orders[0].id,db)
        assert [x.number for x in from_order.deliveries]==["DEL-T201"]
        assert [x.number for x in from_order.invoices]==["IVD-T301"]
        assert [(x.number,x.status) for x in from_order.supplier_bills]==[("APB-T401","cancelled")]
        from_delivery=get_related_documents("delivery",delivery.id,db)
        assert [x.number for x in from_delivery.orders]==["ORD-T101"] and [x.number for x in from_delivery.invoices]==["IVD-T301"]
        from_invoice=get_related_documents("invoice",invoice.id,db)
        assert [x.number for x in from_invoice.orders]==["ORD-T101","ORD-T102"]
        assert len(from_invoice.orders)==2 and from_invoice.invoices[0].status=="draft"
        from_bill=get_related_documents("supplier_bill",bill.id,db)
        assert [x.number for x in from_bill.orders]==["ORD-T101"]
        assert [x.number for x in from_bill.deliveries]==["DEL-T201"] and [x.number for x in from_bill.invoices]==["IVD-T301"]
