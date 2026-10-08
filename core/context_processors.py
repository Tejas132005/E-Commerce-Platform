def ix_layout(request):
    """Small amount of shared data for the app header / owner menu on every page."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    from store.models import ShopCustomer
    return {'ix_customer_count': ShopCustomer.objects.filter(store_owner=user).count()}
