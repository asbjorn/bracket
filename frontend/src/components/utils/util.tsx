import HCaptcha from '@hcaptcha/react-hcaptcha';
import { Center } from '@mantine/core';
import { useParams } from 'react-router';
import { SWRResponse } from 'swr';

import classes from '@pages/create_account.module.css';

/** A web address from a cup name: "Vårcupen 2027" → "varcupen-2027". */
export function slugify(name: string) {
  return name
    .toLowerCase()
    .replace(/æ/g, 'ae')
    .replace(/ø/g, 'o')
    .replace(/å/g, 'a')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40)
    .replace(/-+$/g, '');
}

export function capitalize(str: string) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

export function getTournamentIdFromRouter() {
  const params = useParams();
  const { id: idString }: any = params;
  const id = parseInt(idString, 10);
  const tournamentData = { id };
  return { id, tournamentData };
}

export function getStageItemIdFromRouter() {
  const params = useParams();
  const { stage_item_id: idString }: any = params;
  return parseInt(idString, 10);
}

export function getTournamentEndpointFromRouter() {
  const params = useParams();
  const { id }: any = params;
  return id;
}

export function responseIsValid(response: SWRResponse | null) {
  return response != null && response.data != null && response.data.data != null;
}

export function getBaseURL() {
  return typeof window !== 'undefined' && window.location.origin ? window.location.origin : '';
}

export const groupBy = (keys: any) => (array: any) =>
  array.reduce((objectsByKeyValue: any, obj: any) => {
    const value = keys.map((key: any) => obj[key]).join('-');
    // eslint-disable-next-line no-param-reassign
    objectsByKeyValue[value] = (objectsByKeyValue[value] || []).concat(obj);
    return objectsByKeyValue;
  }, {});

export function truncateString(input: string, length: number) {
  if (input.length > length + 3) {
    return `${input.slice(0, length)}...`;
  }
  return input;
}

export function HCaptchaInput({
  siteKey,
  setCaptchaToken,
}: {
  siteKey: string | undefined;
  setCaptchaToken: any;
}) {
  if (siteKey == null) return null;
  return (
    <Center className={classes.hcaptcha}>
      <HCaptcha sitekey={siteKey} onVerify={setCaptchaToken} theme="dark" />
    </Center>
  );
}

export interface Pagination {
  offset: number;
  limit: number;
  sort_by: string;
  sort_direction: 'asc' | 'desc';
}

export const setTitle = (title: string) => {
  document.title = title;
};
