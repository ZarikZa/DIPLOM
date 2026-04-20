package com.example.hhdiplom.utils;

import androidx.annotation.NonNull;

import com.example.hhdiplom.api.ApiClient;

/**
 * Единая точка определения роли для UI.
 *
 * Мы различаем:
 *  - APPLICANT (соискатель)
 *  - CONTENT_MANAGER (CM)
 *
 * Бэкенд может отдавать разные значения user_type, поэтому опираемся на employee_role.
 */
public final class RoleUtils {

    public enum AppRole {
        APPLICANT,
        CONTENT_MANAGER,
        OTHER
    }

    private RoleUtils() {}

    @NonNull
    public static AppRole getCurrentRole() {
        String userType = safeLower(ApiClient.getUserType());
        String employeeRole = safeLower(ApiClient.getEmployeeRole());

        if (employeeRole.contains("content")) {
            return AppRole.CONTENT_MANAGER;
        }
        if (userType.contains("applicant")) {
            return AppRole.APPLICANT;
        }
        // Если бэкенд пока не отдаёт user_type корректно, но employee_role пустой — считаем соискателем
        if (employeeRole.isEmpty()) {
            return AppRole.APPLICANT;
        }
        return AppRole.OTHER;
    }

    @NonNull
    public static String getDebugRoleString() {
        return "user_type=" + ApiClient.getUserType() +
                ", employee_role=" + ApiClient.getEmployeeRole() +
                ", user_id=" + ApiClient.getUserId() +
                ", applicant_id=" + ApiClient.getApplicantId() +
                ", company_id=" + ApiClient.getCompanyId();
    }

    private static String safeLower(String s) {
        return s == null ? "" : s.trim().toLowerCase();
    }
}
