import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'E-Commerce.settings')
django.setup()

from django.db import transaction
from store.models import Order
from accounts.models import CustomUser

def resequence_orders():
    """
    One-time fix to re-sequence ALL orders based on order_date (ascending).
    Handles unique constraint conflicts by temporary offsetting.
    """
    store_owners = CustomUser.objects.all()
    
    print("Starting re-sequencing process...")
    
    for owner in store_owners:
        # Get active orders sorted by order_date and id
        active_orders = Order.objects.filter(
            store_owner=owner,
            is_deleted=False
        ).order_by('order_date', 'id')
        
        if not active_orders.exists():
            continue
            
        print(f"Processing owner: {owner.username} ({active_orders.count()} active orders)")
        
        with transaction.atomic():
            # 1. First, move ALL orders of this owner to a temporary high range 
            # to avoid IntegrityError during re-numbering.
            all_orders = Order.objects.filter(store_owner=owner)
            for order in all_orders:
                order.order_number = 2000000 + order.id
                order.save(update_fields=['order_number'])
            
            # 2. Re-assign sequential numbers to active orders
            for index, order in enumerate(active_orders, start=1):
                order.order_number = index
                order.invoice_number = f"INV-{index:02d}"
                order.save(update_fields=['order_number', 'invoice_number'])
            
            # 3. Ensure deleted orders are also kept in a unique range 
            # (though they are already in 2,000,000+ from step 1)
            # This just ensures consistency.
            deleted_orders = Order.objects.filter(store_owner=owner, is_deleted=True)
            for d_order in deleted_orders:
                d_order.order_number = 2000000 + d_order.id
                d_order.save(update_fields=['order_number'])

    print("Order resequencing completed successfully.")

if __name__ == "__main__":
    resequence_orders()
