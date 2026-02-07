"""
Environment management API routes.

Provides CRUD operations for environments and variables to manage
different API configurations (e.g., development, staging, production).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.environment import Environment, Variable
from ..schemas.environment import (
    EnvironmentCreate,
    EnvironmentUpdate,
    EnvironmentResponse,
    EnvironmentWithVariables,
    VariableCreate,
    VariableUpdate,
    VariableResponse,
)


router = APIRouter(prefix="/api/environments", tags=["environments"])


# Environment endpoints

@router.post("", response_model=EnvironmentWithVariables, status_code=status.HTTP_201_CREATED)
def create_environment(environment_data: EnvironmentCreate, db: Session = Depends(get_db)):
    """
    Create a new environment with optional initial variables.
    
    If is_active is True, all other environments will be deactivated.
    
    Args:
        environment_data: Environment configuration data including optional variables
        db: Database session
        
    Returns:
        The created environment with assigned ID, timestamps, and variables
    """
    # If this environment should be active, deactivate all others
    if environment_data.is_active:
        db.query(Environment).filter(Environment.is_active == True).update(
            {"is_active": False}
        )
    
    db_environment = Environment(
        name=environment_data.name,
        base_url=environment_data.base_url,
        is_active=environment_data.is_active,
    )
    db.add(db_environment)
    db.flush()  # Get the ID before adding variables
    
    # Add initial variables if provided
    for var_data in environment_data.variables:
        db_variable = Variable(
            environment_id=db_environment.id,
            key=var_data.key,
            value=var_data.value,
        )
        db.add(db_variable)
    
    db.commit()
    db.refresh(db_environment)
    return db_environment


@router.get("", response_model=list[EnvironmentWithVariables])
def list_environments(db: Session = Depends(get_db)):
    """
    List all environments with their variables.
    
    Args:
        db: Database session
        
    Returns:
        List of all environments with their variables
    """
    return db.query(Environment).all()


@router.get("/{environment_id}", response_model=EnvironmentWithVariables)
def get_environment(environment_id: int, db: Session = Depends(get_db)):
    """
    Get an environment by ID with all its variables.
    
    Args:
        environment_id: The unique identifier of the environment
        db: Database session
        
    Returns:
        The environment with all its variables
        
    Raises:
        HTTPException: 404 if environment not found
    """
    db_environment = db.query(Environment).filter(Environment.id == environment_id).first()
    if db_environment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Environment with id {environment_id} not found"
        )
    return db_environment


@router.put("/{environment_id}", response_model=EnvironmentWithVariables)
def update_environment(
    environment_id: int,
    environment_data: EnvironmentUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an existing environment.
    
    If is_active is set to True, all other environments will be deactivated.
    
    Args:
        environment_id: The unique identifier of the environment to update
        environment_data: Fields to update (only provided fields are updated)
        db: Database session
        
    Returns:
        The updated environment with all its variables
        
    Raises:
        HTTPException: 404 if environment not found
    """
    db_environment = db.query(Environment).filter(Environment.id == environment_id).first()
    if db_environment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Environment with id {environment_id} not found"
        )
    
    update_data = environment_data.model_dump(exclude_unset=True)
    
    # If setting this environment as active, deactivate all others
    if update_data.get("is_active") is True:
        db.query(Environment).filter(
            Environment.id != environment_id,
            Environment.is_active == True
        ).update({"is_active": False})
    
    for field, value in update_data.items():
        setattr(db_environment, field, value)
    
    db.commit()
    db.refresh(db_environment)
    return db_environment


@router.delete("/{environment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_environment(environment_id: int, db: Session = Depends(get_db)):
    """
    Delete an environment by ID.
    
    This will cascade delete all variables within the environment.
    
    Args:
        environment_id: The unique identifier of the environment to delete
        db: Database session
        
    Raises:
        HTTPException: 404 if environment not found
    """
    db_environment = db.query(Environment).filter(Environment.id == environment_id).first()
    if db_environment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Environment with id {environment_id} not found"
        )
    
    db.delete(db_environment)
    db.commit()
    return None


@router.post("/{environment_id}/activate", response_model=EnvironmentWithVariables)
def activate_environment(environment_id: int, db: Session = Depends(get_db)):
    """
    Set an environment as the active environment.
    
    Only one environment can be active at a time. This will deactivate
    all other environments.
    
    Args:
        environment_id: The unique identifier of the environment to activate
        db: Database session
        
    Returns:
        The activated environment with all its variables
        
    Raises:
        HTTPException: 404 if environment not found
    """
    db_environment = db.query(Environment).filter(Environment.id == environment_id).first()
    if db_environment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Environment with id {environment_id} not found"
        )
    
    # Deactivate all environments
    db.query(Environment).filter(Environment.is_active == True).update({"is_active": False})
    
    # Activate the specified environment
    db_environment.is_active = True
    db.commit()
    db.refresh(db_environment)
    return db_environment


# Variable endpoints

@router.post("/{environment_id}/variables", response_model=VariableResponse, status_code=status.HTTP_201_CREATED)
def add_variable(
    environment_id: int,
    variable_data: VariableCreate,
    db: Session = Depends(get_db)
):
    """
    Add a new variable to an environment.
    
    Args:
        environment_id: The ID of the parent environment
        variable_data: Variable key-value data
        db: Database session
        
    Returns:
        The created variable with assigned ID
        
    Raises:
        HTTPException: 404 if environment not found
    """
    # Verify environment exists
    db_environment = db.query(Environment).filter(Environment.id == environment_id).first()
    if db_environment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Environment with id {environment_id} not found"
        )
    
    db_variable = Variable(
        environment_id=environment_id,
        key=variable_data.key,
        value=variable_data.value,
    )
    db.add(db_variable)
    db.commit()
    db.refresh(db_variable)
    return db_variable


@router.put("/variables/{variable_id}", response_model=VariableResponse)
def update_variable(
    variable_id: int,
    variable_data: VariableUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an existing variable.
    
    Args:
        variable_id: The unique identifier of the variable to update
        variable_data: Fields to update (only provided fields are updated)
        db: Database session
        
    Returns:
        The updated variable
        
    Raises:
        HTTPException: 404 if variable not found
    """
    db_variable = db.query(Variable).filter(Variable.id == variable_id).first()
    if db_variable is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variable with id {variable_id} not found"
        )
    
    update_data = variable_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_variable, field, value)
    
    db.commit()
    db.refresh(db_variable)
    return db_variable


@router.delete("/variables/{variable_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_variable(variable_id: int, db: Session = Depends(get_db)):
    """
    Delete a variable by ID.
    
    Args:
        variable_id: The unique identifier of the variable to delete
        db: Database session
        
    Raises:
        HTTPException: 404 if variable not found
    """
    db_variable = db.query(Variable).filter(Variable.id == variable_id).first()
    if db_variable is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variable with id {variable_id} not found"
        )
    
    db.delete(db_variable)
    db.commit()
    return None
