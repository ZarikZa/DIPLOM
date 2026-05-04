package com.example.hhdiplom.api;

import com.example.hhdiplom.models.*;

import okhttp3.MultipartBody;
import okhttp3.RequestBody;
import retrofit2.Call;
import retrofit2.http.*;

import java.util.List;
import java.util.Map;

public interface ApiService {

    // ============ АУТЕНТИФИКАЦИЯ ============
    @POST("api/user/register_applicant/")
    Call<TokenResponse> register(@Body RegisterRequest registerRequest);

    @POST("api/token/")
    Call<TokenResponse> login(@Body LoginRequest loginRequest);

    @POST("api/token/refresh/")
    Call<TokenResponse> refreshToken(@Body RefreshTokenRequest refreshTokenRequest);

    // ============ ПОЛЬЗОВАТЕЛИ ============
    @GET("api/user/profile/")
    Call<UserProfile> getUserProfile();

    @DELETE("api/user/profile/")
    Call<Void> deleteAccount();

    @POST("api/user/change-password/")
    Call<Void> changePassword(@Body ChangePasswordRequest body);


    @GET("api/content-manager/profile/stats/")
    Call<CmProfileStatsResponse> getCmProfileStats();

    // ============ ЧАТЫ ============
    @GET("api/chats/")
    Call<ChatResponse> getChats();

    @GET("api/chats/{chatId}/messages/")
    Call<List<Message>> getChatMessages(@Path("chatId") int chatId);

    @POST("api/chats/{chatId}/send_message/")
    Call<Message> sendMessage(@Path("chatId") int chatId, @Body SendMessageRequest request);

    // ============ КОМПАНИИ ============
    @PATCH("api/user/profile/")
    Call<UserProfile> updateProfile(@Body UserProfile profile);

    @Multipart
    @PATCH("api/user/profile/")
    Call<UserProfile> uploadProfileAvatar(@Part MultipartBody.Part avatar);

    @GET("api/content-manager/vacancies/")
    Call<VacancyResponse> getContentManagerVacancies(@Query("page") int page);


    @GET("api/skills/")
    Call<SkillsResponse> getSkills();

    @PUT("api/applicants/me/skills/")
    Call<List<ApplicantSkillItem>> saveMySkills(@Body SkillsUpsertRequest body);

    @GET("api/applicants/me/interests/")
    Call<ApplicantInterestsResponse> getMyInterests();

    @PUT("api/applicants/me/interests/")
    Call<ApplicantInterestsResponse> saveMyInterests(@Body ApplicantInterestsUpdateRequest body);

    @GET("api/applicants/me/skill-suggestions/")
    Call<List<ApplicantSkillSuggestionResponse>> getMySkillSuggestions();

    @POST("api/applicants/me/skill-suggestions/")
    Call<ApplicantSkillSuggestionResponse> createSkillSuggestion(@Body ApplicantSkillSuggestionCreateRequest body);

    @GET("api/vacancies/")
    Call<VacancyResponse> getVacancies(@Query("search") String search,@Query("city") String city,@Query("category") String category,@Query("experience") String experience,@Query("work_conditions") String workConditions,@Query("salary_min") Integer salaryMin,@Query("salary_max") Integer salaryMax,@Query("only_favorites") Boolean isFavorite,@Query("recommended") Boolean recommended,@Query("page") int page);

    @GET("api/vacancies/{id}/")
    Call<VacancyDetails> getVacancyDetails(@Path("id") int vacancyId);

    // Умные рекомендации вакансий
    @GET("api/vacancies/work-conditions/")
    Call<List<String>> getWorkConditions();

    // ============ ОТКЛИКИ ============
    @GET("api/responses/")
    Call<ResponsesResponse> getResponses();

    @POST("api/responses/")
    Call<Void> createResponse(@Body ResponseRequest responseRequest);

    @GET("api/responses/{id}/")
    Call<ResponseItem> getResponseDetails(@Path("id") int responseId);

    // Проверка, откликнулся ли пользователь на вакансию
    @GET("api/responses/check/{vacancy_id}/")
    Call<CheckResponse> checkResponse(@Path("vacancy_id") int vacancyId);

    // ============ ВИДЕО ЛЕНТА ============
    @GET("api/feed/videos/recommended/")
    Call<com.example.hhdiplom.models.FeedVideoResponse> getRecommendedVideoFeed();

    @GET("api/feed/videos/")
    Call<com.example.hhdiplom.models.FeedVideoResponse> getVideoFeed();

    @POST("api/feed/videos/{id}/like/")
    Call<LikeResponse> likeVideo(@Path("id") int videoId);

    @POST("api/feed/videos/{id}/view/")
    Call<Void> viewVideo(@Path("id") int videoId);

    // ============ ИЗБРАННОЕ ============
    @POST("api/favorites/toggle/")
    Call<ToggleFavoriteResponse> toggleFavorite(@Body ToggleFavoriteRequest body);


    @GET("api/applicants/me/skills/")
    Call<List<ApplicantSkill>> getMySkills();

    // ============ CONTENT MANAGER ============
    @GET("api/content-manager/videos/")
    Call<CmVideoResponse> getContentManagerVideos(@Query("page") int page);

    // ============ ЖАЛОБЫ ============
    @POST("api/complaints/")
    Call<Complaint> createComplaint(@Body ComplaintCreateRequest body);

    @GET("api/complaints/")
    Call<ComplaintListResponse> getMyComplaints(@Query("vacancy") int vacancyId);

    // Загрузка видео через CM-эндпоинт (камера/галерея)
    @Multipart
    @POST("api/content-manager/videos/")
    Call<VacancyVideo> uploadVideoAsCM(@Part MultipartBody.Part video,@Part("vacancy") RequestBody vacancyId,@Part("description") RequestBody description);



    @DELETE("api/content-manager/videos/{id}/")
    Call<Void> deleteCmVideo(@Path("id") int videoId);

    @POST("api/auth/password-reset/request/")
    Call<Void> passwordResetRequest(@Body PasswordResetRequest body);

    @POST("api/auth/password-reset/confirm/")
    Call<Void> passwordResetConfirm(@Body PasswordResetConfirm body);

}
