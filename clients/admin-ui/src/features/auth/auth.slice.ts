import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

import type { RootState } from "~/app/store";
import { BASE_URL } from "~/constants";
import { addCommonHeaders } from "~/features/common/CommonHeaders";
import { utf8ToB64 } from "~/features/common/utils";
import { User } from "~/features/user-management/types";
import { RoleRegistryEnum, ScopeRegistryEnum } from "~/types/api";

import {
  LoginRequest,
  LoginResponse,
  LogoutRequest,
  LogoutResponse,
} from "./types";

export interface AuthState {
  user: User | null;
  token: string | null;
}

const initialState: AuthState = {
  token: null,
  user: null,
};

// Auth slice
export const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    login(draftState, action: PayloadAction<LoginResponse>) {
      draftState.user = action.payload.user_data;
      draftState.token = action.payload.token_data.access_token;
    },
    logout(draftState) {
      draftState.user = null;
      draftState.token = null;
    },
  },
});

export const selectAuth = (state: RootState) => state.auth;
export const selectUser = (state: RootState) => selectAuth(state).user;
export const selectToken = (state: RootState) => selectAuth(state).token;

export const { login, logout } = authSlice.actions;

type RoleToScopes = Record<RoleRegistryEnum, ScopeRegistryEnum[]>;

// Auth API
export const authApi = createApi({
  reducerPath: "authApi",
  baseQuery: fetchBaseQuery({
    baseUrl: BASE_URL,
    prepareHeaders: (headers, { getState }) => {
      const token: string | null = selectToken(getState() as RootState);
      addCommonHeaders(headers, token);
      return headers;
    },
  }),
  tagTypes: ["Auth", "Roles"],
  endpoints: (build) => ({
    login: build.mutation<LoginResponse, LoginRequest>({
      query: (credentials) => ({
        url: "login",
        method: "POST",
        body: { ...credentials, password: utf8ToB64(credentials.password) },
      }),
      invalidatesTags: () => ["Auth"],
    }),
    logout: build.mutation<LogoutResponse, LogoutRequest>({
      query: () => ({
        url: "logout",
        method: "POST",
      }),
      invalidatesTags: () => ["Auth"],
    }),
    getRolesToScopesMapping: build.query<RoleToScopes, void>({
      query: () => ({ url: `oauth/role` }),
      providesTags: ["Roles"],
    }),
  }),
});

export const {
  useLoginMutation,
  useLogoutMutation,
  useGetRolesToScopesMappingQuery,
} = authApi;
export const { reducer } = authSlice;
