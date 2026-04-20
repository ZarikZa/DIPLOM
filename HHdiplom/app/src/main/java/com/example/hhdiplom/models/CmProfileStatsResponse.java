package com.example.hhdiplom.models;

import com.google.gson.annotations.SerializedName;

import java.util.List;

public class CmProfileStatsResponse {
    @SerializedName("manager")
    private ManagerInfo manager;

    @SerializedName("company")
    private CompanyInfo company;

    @SerializedName("stats")
    private StatsInfo stats;

    @SerializedName(value = "responses_by_status", alternate = {"responsesByStatus"})
    private List<ResponseStatusItem> responsesByStatus;

    @SerializedName(value = "top_vacancies", alternate = {"topVacancies"})
    private List<TopVacancyItem> topVacancies;

    @SerializedName(value = "chart", alternate = {"chart_data"})
    private ChartInfo chart;

    public ManagerInfo getManager() {
        return manager;
    }

    public CompanyInfo getCompany() {
        return company;
    }

    public StatsInfo getStats() {
        return stats;
    }

    public List<ResponseStatusItem> getResponsesByStatus() {
        return responsesByStatus;
    }

    public List<TopVacancyItem> getTopVacancies() {
        return topVacancies;
    }

    public ChartInfo getChart() {
        return chart;
    }

    public static class ManagerInfo {
        @SerializedName("id")
        private int id;

        @SerializedName("full_name")
        private String fullName;

        @SerializedName("role")
        private String role;

        @SerializedName("email")
        private String email;

        @SerializedName("phone")
        private String phone;

        public int getId() {
            return id;
        }

        public String getFullName() {
            return fullName;
        }

        public String getRole() {
            return role;
        }

        public String getEmail() {
            return email;
        }

        public String getPhone() {
            return phone;
        }
    }

    public static class CompanyInfo {
        @SerializedName("id")
        private int id;

        @SerializedName("name")
        private String name;

        @SerializedName("number")
        private String number;

        @SerializedName("industry")
        private String industry;

        @SerializedName("description")
        private String description;

        public int getId() {
            return id;
        }

        public String getName() {
            return name;
        }

        public String getNumber() {
            return number;
        }

        public String getIndustry() {
            return industry;
        }

        public String getDescription() {
            return description;
        }
    }

    public static class StatsInfo {
        @SerializedName("videos_count")
        private int videosCount;

        @SerializedName("vacancies_count")
        private int vacanciesCount;

        @SerializedName("responses_count")
        private int responsesCount;

        @SerializedName("video_views_count")
        private int videoViewsCount;

        @SerializedName("video_likes_count")
        private int videoLikesCount;

        @SerializedName("vacancy_views_count")
        private int vacancyViewsCount;

        public int getVideosCount() {
            return videosCount;
        }

        public int getVacanciesCount() {
            return vacanciesCount;
        }

        public int getResponsesCount() {
            return responsesCount;
        }

        public int getVideoViewsCount() {
            return videoViewsCount;
        }

        public int getVideoLikesCount() {
            return videoLikesCount;
        }

        public int getVacancyViewsCount() {
            return vacancyViewsCount;
        }
    }

    public static class ResponseStatusItem {
        @SerializedName(value = "status", alternate = {"status_name", "status__status_response_name", "name"})
        private String status;

        @SerializedName(value = "count", alternate = {"responses_count", "total", "value"})
        private int count;

        public String getStatus() {
            return status;
        }

        public int getCount() {
            return count;
        }
    }

    public static class TopVacancyItem {
        @SerializedName(value = "vacancy_id", alternate = {"vacancy", "id"})
        private int vacancyId;

        @SerializedName(value = "position", alternate = {"vacancy__position", "vacancy_title", "title"})
        private String position;

        @SerializedName(value = "responses_count", alternate = {"count", "responses", "total"})
        private int responsesCount;

        public int getVacancyId() {
            return vacancyId;
        }

        public String getPosition() {
            return position;
        }

        public int getResponsesCount() {
            return responsesCount;
        }
    }

    public static class ChartInfo {
        @SerializedName(value = "labels", alternate = {"titles", "x", "chart_labels"})
        private List<String> labels;

        @SerializedName(value = "values", alternate = {"data", "counts", "chart_values"})
        private List<Integer> values;

        public List<String> getLabels() {
            return labels;
        }

        public List<Integer> getValues() {
            return values;
        }
    }
}
