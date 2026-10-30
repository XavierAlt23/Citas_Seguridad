from django.db import migrations

SQL = '''
CREATE FUNCTION deny_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Audit events are append only';
END; $$;
CREATE TRIGGER protect_audit BEFORE UPDATE OR DELETE ON app_audit
FOR EACH ROW EXECUTE FUNCTION deny_audit_mutation();
'''

class Migration(migrations.Migration):
    dependencies = [('app', '0001_initial')]
    operations = [migrations.RunSQL(SQL, 'DROP TRIGGER protect_audit ON app_audit; DROP FUNCTION deny_audit_mutation();')]
