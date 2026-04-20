package com.example.hhdiplom.models;


public class PasswordResetConfirm {
    private String email;
    private String code;
    private String new_password;

    public PasswordResetConfirm(String email, String code, String newPassword){
        this.email = email;
        this.code = code;
        this.new_password = newPassword;
    }
}