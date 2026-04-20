package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class ChangePasswordRequest {
    @SerializedName("old_password")
    private String oldPassword;

    @SerializedName("new_password")
    private String newPassword;

    @SerializedName("new_password_confirm")
    private String newPasswordConfirm;

    public ChangePasswordRequest(String oldPassword, String newPassword, String newPasswordConfirm) {
        this.oldPassword = oldPassword;
        this.newPassword = newPassword;
        this.newPasswordConfirm = newPasswordConfirm;
    }

    public String getOldPassword() {
        return oldPassword;
    }

    public void setOldPassword(String oldPassword) {
        this.oldPassword = oldPassword;
    }

    public String getNewPassword() {
        return newPassword;
    }

    public void setNewPassword(String newPassword) {
        this.newPassword = newPassword;
    }

    public String getNewPasswordConfirm() {
        return newPasswordConfirm;
    }

    public void setNewPasswordConfirm(String newPasswordConfirm) {
        this.newPasswordConfirm = newPasswordConfirm;
    }
}
