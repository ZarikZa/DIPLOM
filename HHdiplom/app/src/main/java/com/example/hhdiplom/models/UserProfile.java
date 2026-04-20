package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

/**
 * Профиль пользователя.
 *
 * Важно: CM (Content Manager) — это сотрудник компании, поэтому:
 *  - user_type обычно "staff" (или иной тип, который отдаёт бэкенд)
 *  - employee_role = "content_manager"
 */
public class UserProfile {

    @SerializedName("id")
    private int id;

    @SerializedName("email")
    private String email;

    @SerializedName("username")
    private String username;

    @SerializedName("phone")
    private String phone;

    @SerializedName("user_type")
    private String userType;

    @SerializedName("user_type_display")
    private String userTypeDisplay;

    @SerializedName("first_name")
    private String firstName;

    @SerializedName("last_name")
    private String lastName;

    @SerializedName("birth_date")
    private String birthDate;

    @SerializedName("resume")
    private String resume;

    @SerializedName("avatar")
    private String avatar;

    // applicant_id может быть null для сотрудников
    @SerializedName("applicant_id")
    private Integer applicantId;

    // Для сотрудников компании
    @SerializedName("employee_role")
    private String employeeRole;

    @SerializedName("company_id")
    private Integer companyId;

    @SerializedName("company_name")
    private String companyName;

    @SerializedName("company_number")
    private String companyNumber;

    @SerializedName("company_industry")
    private String companyIndustry;

    @SerializedName("company_description")
    private String companyDescription;

    // ===== getters =====
    public int getId() { return id; }
    public String getEmail() { return email; }
    public String getUsername() { return username; }
    public String getPhone() { return phone; }
    public String getUserType() { return userType; }
    public String getUserTypeDisplay() { return userTypeDisplay; }
    public String getFirstName() { return firstName; }
    public String getLastName() { return lastName; }
    public String getBirthDate() { return birthDate; }
    public String getResume() { return resume; }
    public String getAvatar() { return avatar; }
    public Integer getApplicantId() { return applicantId; }
    public String getEmployeeRole() { return employeeRole; }
    public Integer getCompanyId() { return companyId; }
    public String getCompanyName() { return companyName; }
    public String getCompanyNumber() { return companyNumber; }
    public String getCompanyIndustry() { return companyIndustry; }
    public String getCompanyDescription() { return companyDescription; }

    // ===== setters (нужны для локального сохранения/моков) =====
    public void setId(int id) { this.id = id; }
    public void setEmail(String email) { this.email = email; }
    public void setUsername(String username) { this.username = username; }
    public void setPhone(String phone) { this.phone = phone; }
    public void setUserType(String userType) { this.userType = userType; }
    public void setUserTypeDisplay(String userTypeDisplay) { this.userTypeDisplay = userTypeDisplay; }
    public void setFirstName(String firstName) { this.firstName = firstName; }
    public void setLastName(String lastName) { this.lastName = lastName; }
    public void setBirthDate(String birthDate) { this.birthDate = birthDate; }
    public void setResume(String resume) { this.resume = resume; }
    public void setAvatar(String avatar) { this.avatar = avatar; }
    public void setApplicantId(Integer applicantId) { this.applicantId = applicantId; }
    public void setEmployeeRole(String employeeRole) { this.employeeRole = employeeRole; }
    public void setCompanyId(Integer companyId) { this.companyId = companyId; }
    public void setCompanyName(String companyName) { this.companyName = companyName; }
    public void setCompanyNumber(String companyNumber) { this.companyNumber = companyNumber; }
    public void setCompanyIndustry(String companyIndustry) { this.companyIndustry = companyIndustry; }
    public void setCompanyDescription(String companyDescription) { this.companyDescription = companyDescription; }
}
