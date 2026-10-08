def is_admin_user(user):
    return user.is_authenticated and user.is_admin


def can_manage_workbook(user, workbook):
    return is_admin_user(user) or (user.is_authenticated and user.role == "moderator" and workbook.moderator_id == user.pk)


def can_edit_workbook(user, workbook):
    return is_admin_user(user) or (can_manage_workbook(user, workbook) and not workbook.is_confirmed)
