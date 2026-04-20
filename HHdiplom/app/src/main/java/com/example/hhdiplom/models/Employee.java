package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

public class Employee {
    @SerializedName("id")
    private int id;

    @SerializedName("user")
    private int userId;

    @SerializedName("first_name")
    private String firstName;

    @SerializedName("last_name")
    private String lastName;

    @SerializedName("company")
    private Integer companyId;

    @SerializedName("access_level")
    private String accessLevel;

    @SerializedName("theme")
    private String theme;

    public int getId() { return id; }
    public void setId(int id) { this.id = id; }

    public int getUserId() { return userId; }
    public void setUserId(int userId) { this.userId = userId; }

    public String getFirstName() { return firstName; }
    public void setFirstName(String firstName) { this.firstName = firstName; }

    public String getLastName() { return lastName; }
    public void setLastName(String lastName) { this.lastName = lastName; }

    public Integer getCompanyId() { return companyId; }
    public void setCompanyId(Integer companyId) { this.companyId = companyId; }

    public String getAccessLevel() { return accessLevel; }
    public void setAccessLevel(String accessLevel) { this.accessLevel = accessLevel; }

    public String getTheme() { return theme; }
    public void setTheme(String theme) { this.theme = theme; }
}