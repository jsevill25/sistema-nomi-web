# Nómina Clara

Aplicación web modular para gestionar nómina de instituciones educativas venezolanas. Calcula conceptos pactados en USD y pagados en bolívares, conserva la tasa BCV usada y permite mantener parámetros institucionales y legales por fecha de vigencia.

> **Uso responsable:** los parámetros de retención y los criterios laborales deben ser revisados por un especialista venezolano antes de utilizarlos para pagos reales. El sistema no certifica el cumplimiento legal ni consulta automáticamente la tasa del BCV.

## Inicio rápido

Requisitos: Python 3.12 o superior y conexión a internet para cargar Bootstrap y las fuentes del navegador.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abre `http://127.0.0.1:8000/` e inicia sesión con el usuario creado. La consola administrativa está en `/admin/`.

## Puesta en marcha

1. Desde el panel admin, crea al menos una versión de **Parámetros legales globales** con vigencia, salario mínimo de referencia, tasas y topes verificados. No se precargan porcentajes legales porque cambian y deben confirmarse antes de operar.
2. En la aplicación, crea el liceo y su primera configuración. El usuario que lo crea recibe el rol de administrador de ese liceo.
3. Registra empleados. Para un docente por hora, completa horas mensuales y valor hora; para contratos mensuales, completa el sueldo mensual. Los bonos regulares se expresan en USD.
4. Procesa una nómina mensual. El sistema elige la política institucional y el conjunto legal vigentes para la fecha de cierre, calcula y persiste el detalle.

## Arquitectura

```text
config/          Ajustes, URLs y dashboard
institutions/    Liceos, políticas versionadas y membresías por tenant
employees/       Contratos administrativos, obreros y docentes
payroll/         Reglas legales, cálculo puro, servicio transaccional y resultados
templates/       Plantillas Bootstrap
static/css/      Identidad visual de la aplicación
```

- `payroll/calculations.py` contiene funciones puras que reciben dataclasses y `Decimal`; no consulta la base de datos.
- `payroll/services.py` selecciona configuraciones vigentes y coordina el guardado transaccional de la corrida.
- Las políticas por liceo y los parámetros legales globales tienen fecha efectiva. Las corridas conservan referencias y una copia de la tasa BCV utilizada.
- `InstitutionMembership` separa los datos entre liceos. Los roles son administrador, operador y solo lectura. El superusuario administra reglas legales y usuarios globales.
- SQLite se configura para desarrollo. Para despliegue SaaS, configura PostgreSQL y HTTPS mediante las variables de entorno y la infraestructura de producción.

## Cálculos incluidos

- Contratos mensuales: sueldo fijo mensual. Docente por hora: horas del mes por valor hora. Tiempo completo: sueldo más escalafón cuando la política lo activa.
- Salario normal: sueldo base más bonos regulares; el transporte entra solo cuando el liceo lo configura como salarial.
- Salario diario normal: salario normal mensual dividido entre 30. Utilidades y bono vacacional diarios: días configurados divididos entre 360, multiplicados por el salario diario. El salario integral diario suma los componentes.
- Cestaticket: monto USD configurado por la tasa BCV; se presenta separadamente del salario normal.
- Prestaciones: registra 15 días por trimestre y permite el abono de días adicionales al aniversario; compara el acumulado contra 30 días por año de servicio multiplicados por el último salario integral diario.
- Retenciones: calcula sobre salario normal y permite pasar `period_weeks` para bases semanales o mensuales. Tasas, topes y salario de referencia proceden del registro global efectivo.

El incremento anual del bono vacacional es configurable y no se codifica un máximo institucional. El incremento de días de prestaciones, su tope y las tasas de retención también se parametrizan. La aplicación no automatiza criterios legales que requieren confirmación externa, ni consulta BCV, exporta archivos bancarios o gestiona pagos.

## Administración y seguridad

- Administra reglas legales desde `/admin/` con una cuenta superusuario.
- Para invitar operadores o visores, crea una cuenta y una membresía a la institución desde el panel admin.
- Los operadores pueden registrar empleados y procesar nóminas. Los administradores de liceo pueden además crear políticas. Los visores son de solo lectura.
- En producción, establece `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0` y `DJANGO_ALLOWED_HOSTS`; sirve estáticos localmente con el pipeline de despliegue y configura cookies seguras, HTTPS, respaldos y PostgreSQL.
- Los resultados son estimaciones sujetas a parámetros configurados. Antes de efectuar pagos o liquidaciones, valida tasas, bases contributivas, topes, redondeos y el tratamiento de cada concepto con asesoría laboral y contable.

## Verificación

```bash
python manage.py check
python manage.py test payroll
```

Las pruebas cubren conversiones, docentes por hora, transporte salarial, escalafón, retenciones semanales/mensuales, tope de días adicionales, comparador de prestaciones y aislamiento entre instituciones.