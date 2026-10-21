import uuid

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class Workspace(models.Model):
    name = models.CharField(max_length=120)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='owned_workspaces')
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='workspaces', blank=True)
    is_personal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name', 'id']
        constraints = [models.UniqueConstraint(fields=['owner'], condition=models.Q(is_personal=True), name='work_personal_workspace_unique')]

    def __str__(self):
        return self.name


class Project(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT, related_name='projects')
    name = models.CharField(max_length=120)
    key = models.CharField(max_length=12)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='owned_projects')
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='work_projects')
    next_number = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name', 'id']
        constraints = [models.UniqueConstraint(fields=['workspace', 'key'], name='work_project_workspace_key_unique')]

    def __str__(self):
        return f'{self.key} · {self.name}'


class Status(models.Model):
    class Category(models.TextChoices):
        OPEN = 'open', 'Offen'
        IN_PROGRESS = 'in_progress', 'In Arbeit'
        DONE = 'done', 'Erledigt'
        CLOSED = 'closed', 'Geschlossen'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='statuses')
    name = models.CharField(max_length=60)
    category = models.CharField(max_length=20, choices=Category.choices)
    position = models.PositiveIntegerField(default=0)
    is_base = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint('project', Lower('name'), name='work_status_name_unique'),
            models.UniqueConstraint(fields=['project', 'category'], condition=models.Q(is_base=True), name='work_status_base_unique'),
            models.CheckConstraint(condition=models.Q(category__in=['open', 'in_progress', 'done', 'closed']), name='work_status_category_valid'),
        ]

    def __str__(self):
        return self.name


class Tag(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tags')
    name = models.CharField(max_length=40)

    class Meta:
        ordering = ['name', 'id']
        constraints = [models.UniqueConstraint('project', Lower('name'), name='work_tag_name_unique')]

    def __str__(self):
        return self.name


class Ticket(models.Model):
    class Kind(models.TextChoices):
        EPIC = 'epic', 'Epic'
        TICKET = 'ticket', 'Ticket'

    class Priority(models.TextChoices):
        LOW = 'low', 'Niedrig'
        NORMAL = 'normal', 'Normal'
        HIGH = 'high', 'Hoch'
        URGENT = 'urgent', 'Dringend'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tickets')
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.TICKET)
    parent = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='children')
    status = models.ForeignKey(Status, on_delete=models.PROTECT, related_name='tickets')
    assignees = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='assigned_tickets')
    tags = models.ManyToManyField(Tag, blank=True, related_name='tickets')
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    due_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_tickets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        constraints = [models.UniqueConstraint(fields=['project', 'number'], name='work_ticket_number_unique')]
        indexes = [models.Index(fields=['project', 'status'], name='work_ticket_board')]

    def __str__(self):
        return f'{self.project.key}-{self.number} · {self.title}'


class TimeEntry(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name='time_entries')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='time_entries', null=True)
    external_person = models.ForeignKey('ClickUpPerson', on_delete=models.PROTECT, null=True, blank=True, related_name='time_entries')
    clickup_source = models.ForeignKey('ClickUpTimeSource', on_delete=models.PROTECT, null=True, blank=True, related_name='segments')
    duration_ms = models.PositiveBigIntegerField(null=True, blank=True)
    work_date = models.DateField()
    minutes = models.PositiveSmallIntegerField()
    note = models.TextField(blank=True, max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-work_date', '-created_at', '-id']
        constraints = [
            models.CheckConstraint(condition=models.Q(minutes__gte=1, minutes__lte=1440), name='work_time_minutes_valid'),
            models.CheckConstraint(condition=(models.Q(user__isnull=False, external_person__isnull=True) | models.Q(user__isnull=True, external_person__isnull=False, clickup_source__isnull=False)), name='work_time_person_valid'),
            models.CheckConstraint(condition=(models.Q(duration_ms__isnull=True, clickup_source__isnull=True) | models.Q(duration_ms__isnull=False, duration_ms__gte=1, duration_ms__lte=86400000, clickup_source__isnull=False)), name='work_time_precision_valid'),
        ]
        indexes = [
            models.Index(fields=['ticket', 'work_date'], name='work_time_ticket_date'),
            models.Index(fields=['user', 'work_date'], name='work_time_user_date'),
        ]


class JiraConnection(models.Model):
    workspace = models.OneToOneField(Workspace, on_delete=models.CASCADE, related_name='jira_connection')
    base_url = models.URLField(max_length=250)
    email = models.EmailField()
    cloud_id = models.CharField(max_length=36, blank=True)
    credential = models.OneToOneField('integrations.IntegrationCredential', on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)


class JiraProject(models.Model):
    connection = models.ForeignKey(JiraConnection, on_delete=models.CASCADE, related_name='project_links')
    remote_id = models.CharField(max_length=100)
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='jira_source')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['connection', 'remote_id'], name='work_jira_project_unique')]


class JiraIssue(models.Model):
    connection = models.ForeignKey(JiraConnection, on_delete=models.CASCADE, related_name='issue_links')
    remote_id = models.CharField(max_length=100)
    remote_key = models.CharField(max_length=100)
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name='jira_source')
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['connection', 'remote_id'], name='work_jira_issue_unique')]


class ClickUpConnection(models.Model):
    workspace = models.OneToOneField(Workspace, on_delete=models.CASCADE, related_name='clickup_connection')
    remote_user_id = models.CharField(max_length=100)
    account_name = models.CharField(max_length=200)
    credential = models.OneToOneField('integrations.IntegrationCredential', on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)


class ClickUpProject(models.Model):
    connection = models.ForeignKey(ClickUpConnection, on_delete=models.CASCADE, related_name='project_links')
    remote_list_id = models.CharField(max_length=100)
    remote_team_id = models.CharField(max_length=100)
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='clickup_source')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['connection', 'remote_list_id'], name='work_clickup_list_unique')]


class ClickUpTask(models.Model):
    connection = models.ForeignKey(ClickUpConnection, on_delete=models.CASCADE, related_name='task_links')
    remote_id = models.CharField(max_length=100)
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name='clickup_source')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['connection', 'remote_id'], name='work_clickup_task_unique')]


class ClickUpPerson(models.Model):
    connection = models.ForeignKey(ClickUpConnection, on_delete=models.CASCADE, related_name='people')
    remote_id = models.CharField(max_length=100)
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['connection', 'remote_id'], name='work_clickup_person_unique')]


class ClickUpTimeSource(models.Model):
    connection = models.ForeignKey(ClickUpConnection, on_delete=models.CASCADE, related_name='time_sources')
    remote_id = models.CharField(max_length=100)
    ticket = models.ForeignKey(Ticket, on_delete=models.PROTECT, related_name='clickup_time_sources')
    person = models.ForeignKey(ClickUpPerson, on_delete=models.PROTECT)
    start_ms = models.BigIntegerField()
    end_ms = models.BigIntegerField()
    duration_ms = models.PositiveBigIntegerField()
    description = models.TextField(blank=True)
    fingerprint = models.CharField(max_length=64)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['connection', 'remote_id'], name='work_clickup_time_unique')]


class ClickUpImportBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(ClickUpConnection, on_delete=models.CASCADE, related_name='import_batches')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    payload = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    expires_at = models.DateTimeField()
    imported_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
