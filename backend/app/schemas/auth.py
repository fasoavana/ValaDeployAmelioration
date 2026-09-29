from pydantic import BaseModel, EmailStr, Field, model_validator, ConfigDict
from datetime import datetime

class UserRegisterSchema(BaseModel):
    full_name : str = Field(min_length=5)
    email  : EmailStr
    password : str = Field(min_length=8)
    confirm_password : str
    
    @model_validator(mode="after")
    def check_password(self):
        if self.password != self.confirm_password :
            raise ValueError("Passwords do not match")
        return self 

# converti un objet SQLALchemy User en response 
class UserResponseSchema(BaseModel):
    id : int
    full_name : str 
    email : EmailStr
    role : str 
    is_active : bool 
    must_change_password: bool 
    created_at : datetime
    
    model_config = ConfigDict(from_attributes=True) 
    
class LoginSchema(BaseModel):
    email : EmailStr
    password : str 

class TokenSchema(BaseModel):
    access_token: str
    token_type: str
    
class ChangePasswordSchema(BaseModel):
    old_password: str
    new_password: str