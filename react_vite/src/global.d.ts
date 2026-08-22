declare global {
  interface Document {
    configuration: {
      is_superuser: boolean;
      isAuthenticated: boolean;
      isOrganizer: boolean;
      showCimaTaskTypes?: boolean;
      visibleTaskTypeGroups?: string[];
      gateCimaTaskVisibility?: boolean;
      STATIC_FILE_LOCATION: string;
      contest_list_version?: string;
    };
  }
}

export {};
