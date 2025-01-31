#!/usr/bin/env python3
import typer
import rich
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, field_validator
import json
import os

# Initialize Typer app and Rich console
app = typer.Typer()
console = Console()

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class TaskModel(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    priority: Priority
    deadline: Optional[datetime] = None
    dependencies: List[str] = Field(default_factory=list)
    recurring: bool = False
    recurrence_interval: Optional[int] = Field(None, ge=1, le=365)
    completed: bool = False
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator('deadline')
    def deadline_must_be_future(cls, v):
        if v and v < datetime.now():
            raise ValueError('Deadline must be in the future')
        return v

    @field_validator('recurrence_interval')
    def validate_recurrence_interval(cls, v, values):
        if values.get('recurring', False) and v is None:
            raise ValueError('Recurrence interval is required for recurring tasks')
        if not values.get('recurring', False) and v is not None:
            raise ValueError('Recurrence interval should only be set for recurring tasks')
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class TaskManager:
    def __init__(self, filename="tasks.json"):
        self.filename = filename
        self.tasks: Dict[str, TaskModel] = {}
        self.load_tasks()

    def load_tasks(self):
        if os.path.exists(self.filename):
            with open(self.filename, "r") as f:
                data = json.load(f)
                self.tasks = {
                    title: TaskModel.parse_obj(task_data)
                    for title, task_data in data.items()
                }

    def save_tasks(self):
        with open(self.filename, "w") as f:
            json.dump(
                {title: json.loads(task.json()) for title, task in self.tasks.items()},
                f,
                indent=2
            )

    def add_task(self, task: TaskModel) -> bool:
        if task.title in self.tasks:
            return False
        if any(dep not in self.tasks for dep in task.dependencies):
            return False
        self.tasks[task.title] = task
        self.save_tasks()
        return True

    def complete_task(self, title: str) -> bool:
        if title not in self.tasks:
            return False
        task = self.tasks[title]
        task.completed = True
        
        if task.recurring and task.recurrence_interval:
            new_deadline = task.deadline + timedelta(days=task.recurrence_interval) if task.deadline else None
            try:
                new_task = TaskModel(
                    title=f"{task.title} (Recurring)",
                    priority=task.priority,
                    deadline=new_deadline,
                    dependencies=task.dependencies,
                    recurring=True,
                    recurrence_interval=task.recurrence_interval
                )
                self.add_task(new_task)
            except ValueError as e:
                console.print(f"[yellow]Warning: Could not create recurring task: {str(e)}[/yellow]")
        
        self.save_tasks()
        return True

    def get_pending_dependencies(self, title: str) -> List[str]:
        if title not in self.tasks:
            return []
        task = self.tasks[title]
        return [dep for dep in task.dependencies if not self.tasks[dep].completed]

task_manager = TaskManager()

def validate_dependencies(dependencies: List[str]) -> bool:
    return all(dep in task_manager.tasks for dep in dependencies)

@app.command()
def add(
    title: str = typer.Option(..., "-t", "--title"),
    priority: Priority = typer.Option(Priority.MEDIUM, "-p", "--priority"),
    deadline: Optional[str] = typer.Option(None, "-d", "--deadline"),
    deps: str = typer.Option("", "-D", "--deps", help="Dependencies (comma-separated)"),
    rec: bool = typer.Option(False, "-r", "--recurring"),
    interval: Optional[int] = typer.Option(None, "-i", "--interval", help="Recurrence interval in days")
):
    """Add a new task to the task manager."""
    try:
        deadline_dt = datetime.fromisoformat(deadline) if deadline else None
        dependencies = [dep.strip() for dep in deps.split(",")] if deps else []
        
        if not validate_dependencies(dependencies):
            console.print("[red]One or more dependencies do not exist![/red]")
            return

        task = TaskModel(
            title=title,
            priority=priority,
            deadline=deadline_dt,
            dependencies=dependencies,
            recurring=rec,
            recurrence_interval=interval if rec else None
        )

        if task_manager.add_task(task):
            console.print(f"[green]Task '{title}' added successfully![/green]")
        else:
            console.print("[red]Failed to add task. Title might be duplicate.[/red]")
            
    except ValueError as e:
        console.print(f"[red]Validation error: {str(e)}[/red]")

@app.command("ls")
def list_tasks():
    """List all tasks with their details."""
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Title")
    table.add_column("Priority")
    table.add_column("Deadline")
    table.add_column("Dependencies")
    table.add_column("Status")
    table.add_column("Recurring")

    for title, task in task_manager.tasks.items():
        status = "[green]Completed[/green]" if task.completed else "[yellow]Pending[/yellow]"
        deadline = task.deadline.strftime("%Y-%m-%d %H:%M") if task.deadline else "No deadline"
        recurring = f"Yes ({task.recurrence_interval} days)" if task.recurring else "No"
        
        table.add_row(
            title,
            task.priority.value,
            deadline,
            ", ".join(task.dependencies) or "None",
            status,
            recurring
        )

    console.print(table)

@app.command("done")
def complete(title: str):
    """Mark a task as completed."""
    pending_deps = task_manager.get_pending_dependencies(title)
    if pending_deps:
        console.print(f"[red]Cannot complete task. Pending dependencies: {', '.join(pending_deps)}[/red]")
        return

    if task_manager.complete_task(title):
        console.print(f"[green]Task '{title}' marked as completed![/green]")
        if task_manager.tasks[title].recurring:
            console.print("[blue]New recurring task created.[/blue]")
    else:
        console.print(f"[red]Task '{title}' not found![/red]")

@app.command("view")
def view(title: str):
    """View detailed information about a specific task."""
    if title not in task_manager.tasks:
        console.print(f"[red]Task '{title}' not found![/red]")
        return

    task = task_manager.tasks[title]
    panel_content = f"""
[bold]Title:[/bold] {task.title}
[bold]Priority:[/bold] {task.priority.value}
[bold]Deadline:[/bold] {task.deadline.strftime('%Y-%m-%d %H:%M') if task.deadline else 'No deadline'}
[bold]Dependencies:[/bold] {', '.join(task.dependencies) or 'None'}
[bold]Status:[/bold] {'Completed' if task.completed else 'Pending'}
[bold]Recurring:[/bold] {'Yes' if task.recurring else 'No'}
[bold]Recurrence Interval:[/bold] {f'{task.recurrence_interval} days' if task.recurring else 'N/A'}
[bold]Created At:[/bold] {task.created_at.strftime('%Y-%m-%d %H:%M')}
    """
    console.print(Panel(panel_content, title=f"Task Details - {title}", border_style="blue"))

if __name__ == "__main__":
    app()
