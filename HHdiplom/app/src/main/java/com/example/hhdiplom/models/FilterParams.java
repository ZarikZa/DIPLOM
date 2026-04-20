package com.example.hhdiplom.models;


public class FilterParams {

    private String search;
    private String city;
    private String category;
    private String experience;
    private String workConditions;
    private Integer salaryMin;
    private Integer salaryMax;
    private boolean onlyFavorites = false;

    public String getSearch() { return search; }
    public void setSearch(String search) { this.search = search != null && !search.isEmpty() ? search : null; }

    public String getCity() { return city; }
    public void setCity(String city) { this.city = city != null && !city.isEmpty() ? city : null; }

    public String getCategory() { return category; }
    public void setCategory(String category) { this.category = category != null && !category.isEmpty() ? category : null; }

    public String getExperience() { return experience; }
    public void setExperience(String experience) { this.experience = experience != null && !experience.isEmpty() ? experience : null; }

    public String getWorkConditions() { return workConditions; }
    public void setWorkConditions(String workConditions) { this.workConditions = workConditions != null && !workConditions.isEmpty() ? workConditions : null; }

    public Integer getSalaryMin() { return salaryMin; }
    public void setSalaryMin(Integer salaryMin) { this.salaryMin = salaryMin; }

    public Integer getSalaryMax() { return salaryMax; }
    public void setSalaryMax(Integer salaryMax) { this.salaryMax = salaryMax; }

    public boolean isOnlyFavorites() { return onlyFavorites; }
    public void setOnlyFavorites(boolean onlyFavorites) { this.onlyFavorites = onlyFavorites; }

    public Boolean getOnlyFavoritesQuery() { return onlyFavorites ? Boolean.TRUE : null; }

    /** 🔑 Очищаем все фильтры */
    public void clear() {
        search = null;
        city = null;
        category = null;
        experience = null;
        workConditions = null;
        salaryMin = null;
        salaryMax = null;
        onlyFavorites = false;
    }
}
